"""Everything that talks to yt-dlp: music search, MP3 download, video download."""
import asyncio
import difflib
import logging
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

from ..config import config
from . import media

log = logging.getLogger(__name__)

_sem = asyncio.Semaphore(max(1, config.max_parallel))

MAX_TRACK_SECONDS = 20 * 60  # longer things are mixes / albums, not songs

_JUNK = re.compile(
    r"\s*[\(\[](?:official\s*)?(?:music\s*|lyrics?\s*|hd\s*|4k\s*|audio\s*|visuali[sz]er\s*|mv\s*|clip\s*|video\s*)+"
    r"(?:video)?[\)\]]",
    re.IGNORECASE,
)


class DownloadFailed(Exception):
    pass


class TooBig(Exception):
    pass


@dataclass
class Track:
    id: str
    title: str
    duration: int = 0
    uploader: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "duration": self.duration, "uploader": self.uploader}


@dataclass
class AudioFile:
    path: Path
    title: str
    performer: str
    duration: int
    thumb: Path | None = None


@dataclass
class VideoResult:
    files: list[Path]
    key: str  # stable cache key, e.g. "youtube:dQw4w9WgXcQ"
    title: str = ""
    track_hint: str = ""  # "Artist - Title" if the platform knows the music
    workdir: Path | None = None
    meta: list[dict] = field(default_factory=list)  # per-file probe info


def _base_opts(workdir: Path | None = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 10,
        "extractor_retries": 3,
        "concurrent_fragment_downloads": 4,
        "geo_bypass": True,
        "noplaylist": True,
        "cachedir": str(config.data_dir / "yt-dlp-cache"),
    }
    if workdir:
        opts["paths"] = {"home": str(workdir), "temp": str(workdir)}
        opts["outtmpl"] = "%(id).80s_%(autonumber)s.%(ext)s"
    if config.cookies:
        opts["cookiefile"] = config.cookies
    if config.pot_url:
        opts["extractor_args"] = {"youtubepot-bgutilhttp": {"base_url": [config.pot_url]}}
    return opts


# ---------------------------------------------------------------- blocked-IP fallbacks
#
# Datacenter IPs (Hetzner, AWS...) are often blocked: YouTube says "Sign in to confirm
# you're not a bot", Instagram asks to log in, TikTok returns empty responses.
# Every request is tried directly first and then through PROXY_URL (Cloudflare WARP in
# docker-compose). If the proxy works and the direct route didn't, the proxy is used
# first for that site for the next hour.

_PREFER_PROXY_FOR = 3600
_proxy_first_until: dict[str, float] = {}

_PERMANENT = ("drm protected", "private video", "video unavailable. this video has been removed", "copyright",
              "this video has been removed", "account associated with this video has been terminated",
              "is not a valid url", "unsupported url", "does not pass filter")


def _site(url: str) -> str:
    m = re.match(r"(?:https?://)?(?:www\.|m\.)?([^/:?#]+)", url)
    host = m.group(1).lower() if m else url
    for key in ("youtube", "youtu.be", "instagram", "tiktok", "soundcloud"):
        if key in host:
            return "youtube" if key == "youtu.be" else key
    if url.startswith("ytsearch"):
        return "youtube"
    if url.startswith("scsearch"):
        return "soundcloud"
    return host


def _routes(url: str) -> list[dict]:
    routes: list[dict] = [{}]
    if config.proxy:
        via = {"proxy": config.proxy}
        if _proxy_first_until.get(_site(url), 0) > time.time():
            routes.insert(0, via)
        else:
            routes.append(via)
    return routes


def _extract(url: str, opts: dict, download: bool = True) -> dict:
    """yt-dlp extract_info with the direct -> proxy fallback (blocking; run in a thread)."""
    last: Exception | None = None
    for extra in _routes(url):
        try:
            with yt_dlp.YoutubeDL(opts | extra) as ydl:
                info = ydl.extract_info(url, download=download)
        except yt_dlp.utils.DownloadError as e:
            last = e
            log.warning("yt-dlp failed (%s) for %s: %s", "proxy" if extra else "direct", url, str(e)[:300])
            if any(p in str(e).lower() for p in _PERMANENT):
                break
            continue
        site = _site(url)
        if extra:
            _proxy_first_until[site] = time.time() + _PREFER_PROXY_FOR
        else:
            _proxy_first_until.pop(site, None)
        return info
    assert last is not None
    raise last


def _new_workdir() -> Path:
    d = config.tmp_dir / uuid.uuid4().hex
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _in_thread(fn, *args):
    async with _sem:
        return await asyncio.to_thread(fn, *args)


# ---------------------------------------------------------------- search

def _search_sync(query: str, limit: int) -> list[Track]:
    opts = _base_opts() | {"extract_flat": "in_playlist", "skip_download": True}
    info = _extract(f"ytsearch{limit}:{query}", opts, download=False)
    tracks: list[Track] = []
    seen: set[str] = set()
    for e in (info or {}).get("entries") or []:
        if not e or not e.get("id") or e["id"] in seen:
            continue
        dur = int(e.get("duration") or 0)
        if dur and dur > MAX_TRACK_SECONDS:
            continue
        if e.get("live_status") in ("is_live", "is_upcoming"):
            continue
        seen.add(e["id"])
        tracks.append(
            Track(id=e["id"], title=(e.get("title") or "").strip(), duration=dur,
                  uploader=(e.get("channel") or e.get("uploader") or "").strip())
        )
    return tracks


async def search(query: str, limit: int = 30) -> list[Track]:
    try:
        return await _in_thread(_search_sync, query, limit)
    except Exception:
        log.exception("search failed: %s", query)
        return []


def clean_title(title: str) -> str:
    """'POP SMOKE - DIOR (OFFICIAL VIDEO) #hashtag' -> 'POP SMOKE - DIOR'"""
    title = _JUNK.sub("", title)
    title = re.sub(r"[#@]\w+", "", title)
    title = re.sub(r"\s*[\(\[][^\)\]]*(?:official|video|lyric|audio|hd|4k|clip)[^\)\]]*[\)\]]", "", title, flags=re.I)
    return re.sub(r"\s+", " ", title).strip(" -|/")


def similarity(a: str, b: str) -> float:
    norm = lambda s: re.sub(r"[^\w]+", " ", s.lower()).strip()
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


async def find_best(title: str, artist: str) -> Track | None:
    """Find the YouTube upload that best matches a recognised song."""
    query = f"{artist} - {title}" if artist else title
    results = await search(query, limit=8)
    if not results:
        return None

    def score(tr: Track) -> float:
        s = similarity(query, _JUNK.sub("", tr.title))
        low = tr.title.lower()
        if title.lower() in low:
            s += 0.3
        if artist and artist.split(",")[0].split("&")[0].strip().lower() in (low + " " + tr.uploader.lower()):
            s += 0.3
        if any(w in low for w in ("cover", "remix", "slowed", "speed up", "sped up", "karaoke", "1 hour", "nightcore")) \
                and not any(w in query.lower() for w in ("cover", "remix", "slowed", "sped")):
            s -= 0.4
        if tr.uploader.lower().endswith("- topic"):
            s += 0.15
        return s

    return max(results, key=score)


# ---------------------------------------------------------------- audio

def split_title(info: dict) -> tuple[str, str]:
    """Return (performer, title) for the MP3 tags."""
    track, artist = info.get("track"), info.get("artist") or (info.get("artists") or [None])[0]
    if track and artist:
        return artist, track
    raw = _JUNK.sub("", info.get("title") or "").strip()
    for sep in (" - ", " – ", " — ", " | "):
        if sep in raw:
            a, t = raw.split(sep, 1)
            return a.strip(), t.strip()
    uploader = re.sub(r"\s*-\s*Topic$|VEVO$", "", info.get("uploader") or info.get("channel") or "").strip()
    return uploader, raw


def _audio_opts(workdir: Path) -> dict:
    return _base_opts(workdir) | {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "writethumbnail": True,
        "match_filter": yt_dlp.utils.match_filter_func(f"duration <? {MAX_TRACK_SECONDS + 60}"),
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"},
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": True},
        ],
    }


def _download_audio_sync(url: str, workdir: Path) -> dict:
    return _extract(url, _audio_opts(workdir), download=True)


async def download_audio(video_id: str, url: str | None = None) -> AudioFile:
    url = url or f"https://www.youtube.com/watch?v={video_id}"
    return await _fetch_audio(url)


def _soundcloud_sync(query: str, workdir: Path) -> dict:
    """Find the song on SoundCloud and download the best matching track.
    Some SoundCloud tracks are DRM-protected (Go+), so several candidates are tried."""
    probe_opts = _base_opts() | {"extract_flat": "in_playlist", "skip_download": True}
    found = _extract(f"scsearch10:{query}", probe_opts, download=False)
    entries = [e for e in (found or {}).get("entries") or [] if e and e.get("url")]
    words = set(re.findall(r"\w{3,}", query.lower()))

    def label(e: dict) -> str:
        return f"{e.get('uploader') or ''} {e.get('title') or ''}"

    candidates = [e for e in entries if not words or words & set(re.findall(r"\w{3,}", label(e).lower()))]
    candidates.sort(key=lambda e: similarity(query, label(e)) + similarity(query, e.get("title") or ""),
                    reverse=True)
    if not candidates:
        raise yt_dlp.utils.DownloadError("no matching track on SoundCloud")
    last: Exception | None = None
    for e in candidates[:4]:
        try:
            return _extract(e["url"], _audio_opts(workdir), download=True)
        except yt_dlp.utils.DownloadError as err:  # DRM / geo-blocked / removed -> next one
            last = err
            for f in workdir.iterdir():
                f.unlink(missing_ok=True)
    raise last


async def download_audio_soundcloud(query: str) -> AudioFile:
    return await _fetch_audio(query, soundcloud=True)


async def _fetch_audio(target: str, soundcloud: bool = False) -> AudioFile:
    workdir = _new_workdir()
    try:
        if soundcloud:
            info = await _in_thread(_soundcloud_sync, target, workdir)
        else:
            info = await _in_thread(_download_audio_sync, target, workdir)
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(workdir, ignore_errors=True)
        raise DownloadFailed(str(e)) from e
    mp3s = sorted(workdir.glob("*.mp3"))
    if not info or not mp3s:
        shutil.rmtree(workdir, ignore_errors=True)
        raise DownloadFailed("filtered out or no mp3 produced")
    performer, title = split_title(info)
    thumb = None
    jpgs = sorted(workdir.glob("*.jpg"))
    if jpgs:
        thumb = await media.image_to_thumb(jpgs[0], workdir / "thumb_tg.jpg")
    return AudioFile(path=mp3s[0], title=title or info.get("title", ""), performer=performer,
                     duration=int(info.get("duration") or 0), thumb=thumb)


# ---------------------------------------------------------------- video

HEIGHTS = (1080, 720, 480, 360)


def _video_opts(workdir: Path, height: int, platform: str) -> dict:
    limit = config.upload_limit
    opts = _base_opts(workdir) | {
        # Prefer H.264 + AAC in MP4: plays inline on every Telegram client (iPhone too).
        "format": (
            f"bv*[height<={height}][filesize<?{limit}]+ba/"
            f"b[height<={height}][filesize<?{limit}]/"
            f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b"
        ),
        "format_sort": [f"res:{height}", "vcodec:h264", "acodec:aac", "ext:mp4:m4a", "size"],
        "merge_output_format": "mp4",
        "max_filesize": limit * 3,  # abort pointless giant downloads early
        "postprocessor_args": {"merger+ffmpeg_o": ["-movflags", "+faststart"]},
    }
    if platform == "instagram":
        # carousels: download every video of the post (Telegram album max 10)
        opts["noplaylist"] = False
        opts["playlistend"] = 10
    return opts


def _download_video_sync(url: str, workdir: Path, height: int, platform: str) -> dict:
    return _extract(url, _video_opts(workdir, height, platform), download=True)


def _looks_big(info: dict) -> bool:
    for e in info.get("entries") or [info]:
        size = (e or {}).get("filesize") or (e or {}).get("filesize_approx") or 0
        if size > config.upload_limit:
            return True
    return False


def _key_for(info: dict, platform: str, url: str) -> str:
    vid = info.get("id") or info.get("display_id")
    return f"{platform}:{vid}" if vid else f"url:{url}"


def _hint_for(info: dict) -> str:
    track = info.get("track")
    artist = info.get("artist") or (info.get("artists") or [None])[0]
    if track and artist and "original sound" not in track.lower():
        return f"{artist} - {track}"
    return ""


async def download_video(url: str, platform: str) -> VideoResult:
    last_err: Exception | None = None
    heights = [h for h in HEIGHTS if h <= config.max_height] or [config.max_height]
    for height in heights:
        workdir = _new_workdir()
        try:
            info = await _in_thread(_download_video_sync, url, workdir, height, platform)
        except yt_dlp.utils.DownloadError as e:
            last_err = e
            msg = str(e).lower()
            shutil.rmtree(workdir, ignore_errors=True)
            if "larger than max-filesize" in msg:
                continue
            raise DownloadFailed(str(e)) from e
        if not info:
            raise DownloadFailed("no info")
        files = sorted(
            p for p in workdir.iterdir()
            if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov", ".jpg", ".jpeg", ".png", ".webp")
            and not p.name.endswith((".part", ".ytdl")) and not p.name.startswith("thumb")
        )
        if not files or any(p.stat().st_size > config.upload_limit for p in files):
            # yt-dlp silently skips files over max_filesize -> try a lower resolution
            shutil.rmtree(workdir, ignore_errors=True)
            last_err = TooBig() if files or _looks_big(info) else DownloadFailed("nothing downloaded")
            continue
        entries = info.get("entries") or [info]
        hint = next((h for h in (_hint_for(e or {}) for e in entries) if h), "")
        return VideoResult(files=files, key=_key_for(info, platform, url),
                           title=info.get("title") or "", track_hint=hint, workdir=workdir)
    if isinstance(last_err, TooBig) or last_err is None:
        raise TooBig()
    raise DownloadFailed(str(last_err))


# ---------------------------------------------------------------- diagnostics (/diag)

def check_route(url: str, use_proxy: bool) -> str | None:
    """Resolve a URL without downloading. Returns None if OK, else a short error."""
    if use_proxy and not config.proxy:
        return "PROXY_URL not set"
    opts = _base_opts() | {"skip_download": True, "format": "bestaudio/best"}
    if url.startswith(("scsearch", "ytsearch")):
        opts["extract_flat"] = "in_playlist"
    if use_proxy:
        opts["proxy"] = config.proxy
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=False)
        return None
    except Exception as e:  # noqa: BLE001
        msg = re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR: ", "")
        return msg[:160]


async def check_route_async(url: str, use_proxy: bool) -> str | None:
    return await asyncio.to_thread(check_route, url, use_proxy)
