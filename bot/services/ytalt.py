"""YouTube through public Invidious / Piped instances.

When YouTube blocks the server IP ("Sign in to confirm you're not a bot") on every
route, the video is fetched from YouTube by an Invidious or Piped server instead and
streamed to us through that server (local=true / Piped proxy). No account, no cookies.
Instances come from the public lists (cached for an hour); YT_ALT_INSTANCES in .env
(comma separated, e.g. https://inv.example.com,piped:https://api.piped.example)
puts your own favourites first.
"""
import json
import logging
import os
import subprocess
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .mp3sites import http_get

log = logging.getLogger(__name__)

INVIDIOUS_LIST = "https://api.invidious.io/instances.json?sort_by=health"
PIPED_LIST = "https://piped-instances.kavin.rocks/"
LIST_TTL = 3600
MAX_INSTANCES = 6
MIN_VIDEO_BYTES = 20 * 1024  # ffmpeg exits 0 with an empty file when a stream breaks
DOWN_PAUSE = 10 * 60  # all instances failed -> don't waste time on them for a while
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"

_cache: dict = {"at": 0.0, "list": []}
_good: list[tuple[str, str]] = []  # instances that worked recently go first
_down_until = 0.0


def reset_pause() -> None:
    global _down_until
    _down_until = 0.0


def available() -> bool:
    return _down_until <= time.time()


@dataclass
class Stream:
    url: str
    mime: str
    height: int = 0
    bitrate: int = 0
    size: int = 0
    video_only: bool = False

    @property
    def is_audio(self) -> bool:
        return self.mime.startswith("audio")

    @property
    def h264(self) -> bool:
        return "avc1" in self.mime or ("mp4" in self.mime and "av01" not in self.mime and "vp9" not in self.mime)


@dataclass
class Info:
    id: str
    title: str
    author: str
    duration: int
    thumb: str
    streams: list[Stream] = field(default_factory=list)
    source: str = ""


def _env_instances() -> list[tuple[str, str]]:
    out = []
    for raw in os.getenv("YT_ALT_INSTANCES", "").split(","):
        raw = raw.strip().rstrip("/")
        if not raw:
            continue
        if raw.startswith("piped:"):
            out.append(("piped", raw[6:]))
        else:
            out.append(("invidious", raw.removeprefix("invidious:")))
    return out


def _public_instances() -> list[tuple[str, str]]:
    if time.time() - _cache["at"] < LIST_TTL and _cache["list"]:
        return _cache["list"]
    found: list[tuple[str, str]] = []
    try:
        data = json.loads(http_get(INVIDIOUS_LIST, timeout=10))
        for name, meta in data:
            if meta.get("type") == "https" and meta.get("api") and meta.get("uri"):
                found.append(("invidious", meta["uri"].rstrip("/")))
    except Exception as e:  # noqa: BLE001
        log.info("invidious list unavailable: %s", str(e)[:120])
    try:
        data = json.loads(http_get(PIPED_LIST, timeout=10))
        for inst in data:
            if inst.get("api_url"):
                found.append(("piped", inst["api_url"].rstrip("/")))
    except Exception as e:  # noqa: BLE001
        log.info("piped list unavailable: %s", str(e)[:120])
    if found:
        _cache.update(at=time.time(), list=found)
    return found or _cache["list"]


def instances() -> list[tuple[str, str]]:
    seen, out = set(), []
    for inst in _env_instances() + _good + _public_instances():
        if inst not in seen:
            seen.add(inst)
            out.append(inst)
    return out[:MAX_INSTANCES + len(_env_instances())]


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _height(s) -> int:
    digits = "".join(ch for ch in str(s or "").split("p")[0] if ch.isdigit())
    return int(digits) if digits else 0


def _invidious(base: str, video_id: str) -> Info:
    data = json.loads(http_get(f"{base}/api/v1/videos/{video_id}?local=true", timeout=8))
    if data.get("error"):
        raise RuntimeError(data["error"])
    streams = []
    for f in data.get("adaptiveFormats") or []:
        if not f.get("url"):
            continue
        mime = f.get("type") or ""
        streams.append(Stream(url=urllib.parse.urljoin(base + "/", f["url"]), mime=mime,
                              height=_height(f.get("resolution") or f.get("qualityLabel")),
                              bitrate=_int(f.get("bitrate")), size=_int(f.get("clen")),
                              video_only=mime.startswith("video")))
    for f in data.get("formatStreams") or []:
        if f.get("url"):
            streams.append(Stream(url=urllib.parse.urljoin(base + "/", f["url"]), mime=f.get("type") or "video/mp4",
                                  height=_height(f.get("resolution") or f.get("qualityLabel")),
                                  size=_int(f.get("clen"))))
    thumbs = data.get("videoThumbnails") or [{}]
    return Info(id=video_id, title=data.get("title") or "", author=data.get("author") or "",
                duration=_int(data.get("lengthSeconds")), thumb=urllib.parse.urljoin(base + "/", thumbs[0].get("url") or ""),
                streams=streams, source=base)


def _piped(base: str, video_id: str) -> Info:
    data = json.loads(http_get(f"{base}/streams/{video_id}", timeout=8))
    if data.get("error"):
        raise RuntimeError(data.get("message") or data["error"])
    streams = []
    for f in data.get("videoStreams") or []:
        if f.get("url"):
            mime = f"{f.get('mimeType') or 'video/mp4'}; codecs=\"{f.get('codec') or ''}\""
            streams.append(Stream(url=f["url"], mime=mime, height=_height(f.get("quality")),
                                  bitrate=_int(f.get("bitrate")), size=_int(f.get("contentLength")),
                                  video_only=bool(f.get("videoOnly"))))
    for f in data.get("audioStreams") or []:
        if f.get("url"):
            streams.append(Stream(url=f["url"], mime=f.get("mimeType") or "audio/mp4",
                                  bitrate=_int(f.get("bitrate")), size=_int(f.get("contentLength"))))
    return Info(id=video_id, title=data.get("title") or "", author=data.get("uploader") or "",
                duration=_int(data.get("duration")), thumb=data.get("thumbnailUrl") or "",
                streams=streams, source=base)


def _ffmpeg(args: list[str], timeout: int = 900) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-user_agent", _UA, *args]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[-300:] or "ffmpeg failed")


def _best_audio(info: Info) -> Stream | None:
    audio = [s for s in info.streams if s.is_audio]
    # m4a first (copies into mp4 without re-encoding), then highest bitrate
    return max(audio, key=lambda s: ("mp4" in s.mime, s.bitrate), default=None)


def _pick_video(info: Info, max_height: int, limit: int) -> tuple[Stream, Stream | None] | None:
    audio = _best_audio(info)
    a_size = audio.size if audio else 0
    vids = [s for s in info.streams if not s.is_audio and s.height and s.height <= max_height]
    adaptive = [s for s in vids if s.video_only and audio]
    muxed = [s for s in vids if not s.video_only]

    def fits(s: Stream) -> bool:
        return not s.size or s.size + (a_size if s.video_only else 0) <= limit

    for s in sorted(adaptive, key=lambda s: (s.height, s.h264, s.bitrate), reverse=True):
        if fits(s):
            return s, audio
    for s in sorted(muxed, key=lambda s: s.height, reverse=True):
        if fits(s):
            return s, None
    return None


def fetch_info(video_id: str) -> Info:
    """First instance that returns playable streams."""
    global _down_until
    if not available():
        raise RuntimeError("Invidious/Piped paused after recent failures")
    errors = []
    for kind, base in instances():
        try:
            info = (_invidious if kind == "invidious" else _piped)(base, video_id)
            if not info.streams:
                raise RuntimeError("no streams")
            if (kind, base) in _good:
                _good.remove((kind, base))
            _good.insert(0, (kind, base))
            del _good[5:]
            return info
        except Exception as e:  # noqa: BLE001
            errors.append(f"{base}: {str(e)[:80]}")
            if (kind, base) in _good:
                _good.remove((kind, base))
    _down_until = time.time() + DOWN_PAUSE
    raise RuntimeError("no Invidious/Piped instance worked: " + " | ".join(errors[-4:]) if errors
                       else "no Invidious/Piped instances known")


def download_video(video_id: str, workdir: Path, max_height: int, limit: int) -> Info:
    """Video (best H.264 that fits the Telegram limit) merged with the best audio -> workdir/<id>.mp4."""
    info = fetch_info(video_id)
    out = workdir / f"{video_id}.mp4"
    tried_heights: list[int] = []
    for height in (max_height, 720, 480, 360):
        if height > max_height or height in tried_heights:
            continue
        tried_heights.append(height)
        choice = _pick_video(info, height, limit)
        if not choice:
            continue
        video, audio = choice
        try:
            if audio:
                _ffmpeg(["-i", video.url, "-i", audio.url, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                         *(["-c:a", "copy"] if "mp4" in audio.mime else ["-c:a", "aac", "-b:a", "160k"]),
                         "-movflags", "+faststart", str(out)])
            else:
                _ffmpeg(["-i", video.url, "-c", "copy", "-movflags", "+faststart", str(out)])
        except Exception as e:  # noqa: BLE001
            log.warning("alt video %sp failed via %s: %s", video.height, info.source, str(e)[:200])
            out.unlink(missing_ok=True)
            continue
        if out.exists() and MIN_VIDEO_BYTES < out.stat().st_size <= limit:
            log.info("YouTube %s via %s (%sp)", video_id, info.source, video.height)
            return info
        out.unlink(missing_ok=True)
    raise RuntimeError(f"no stream fits {limit // (1024 * 1024)} MB via {info.source}")


def download_audio(video_id: str, workdir: Path) -> tuple[Info, Path, Path | None]:
    """Best audio -> workdir/<id>.mp3 (+ cover jpg)."""
    info = fetch_info(video_id)
    audio = _best_audio(info)
    if not audio:
        raise RuntimeError(f"no audio stream via {info.source}")
    out = workdir / f"{video_id}.mp3"
    _ffmpeg(["-i", audio.url, "-vn", "-c:a", "libmp3lame", "-b:a", "320k",
             "-metadata", f"title={info.title}", "-metadata", f"artist={info.author}", str(out)])
    if not out.exists() or out.stat().st_size < MIN_VIDEO_BYTES:
        raise RuntimeError(f"empty audio via {info.source}")
    cover = None
    if info.thumb:
        try:
            img = http_get(info.thumb, timeout=15)
            if len(img) > 1000:
                cover = workdir / "cover.jpg"
                cover.write_bytes(img)
        except Exception:  # noqa: BLE001
            pass
    log.info("YouTube audio %s via %s", video_id, info.source)
    return info, out, cover
