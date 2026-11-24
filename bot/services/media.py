"""ffmpeg / ffprobe helpers."""
import asyncio
import json
from pathlib import Path


async def _run(*args: str, timeout: float = 300) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return proc.returncode, out, err


async def probe(path: Path) -> dict:
    """Return {'duration': float, 'width': int, 'height': int, 'has_audio': bool}."""
    code, out, _ = await _run(
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path), timeout=60
    )
    info = {"duration": 0.0, "width": 0, "height": 0, "has_audio": False, "sample_rate": 0}
    if code != 0:
        return info
    data = json.loads(out or b"{}")
    try:
        info["duration"] = float(data.get("format", {}).get("duration") or 0)
    except ValueError:
        pass
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and not info["width"] \
                and not (s.get("disposition") or {}).get("attached_pic"):
            w, h = int(s.get("width") or 0), int(s.get("height") or 0)
            rot = 0
            for sd in s.get("side_data_list", []) or []:
                if "rotation" in sd:
                    rot = abs(int(sd["rotation"]))
            if rot in (90, 270):
                w, h = h, w
            info["width"], info["height"] = w, h
        elif s.get("codec_type") == "audio":
            info["has_audio"] = True
            info["sample_rate"] = info["sample_rate"] or int(s.get("sample_rate") or 0)
    return info


async def make_thumb(video: Path, out: Path, at: float = 1.0) -> Path | None:
    """Telegram thumbnail: JPEG, max 320px side."""
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", str(video), "-frames:v", "1",
        "-vf", "scale='if(gt(iw,ih),320,-2)':'if(gt(iw,ih),-2,320)'", "-q:v", "4", str(out), timeout=60,
    )
    if code != 0 or not out.exists():
        if at > 0:
            return await make_thumb(video, out, 0)
        return None
    return out


async def image_to_thumb(image: Path, out: Path) -> Path | None:
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(image),
        "-vf", "scale='if(gt(iw,ih),320,-2)':'if(gt(iw,ih),-2,320)'", "-q:v", "4", str(out), timeout=60,
    )
    return out if code == 0 and out.exists() else None


async def extract_audio(src: Path, out: Path, start: float = 0, length: float | None = None,
                        rate: int = 48000, bitrate: str = "96k") -> Path | None:
    """Extract (part of) the audio track to a mono OGG/Opus file (small, good enough for recognition)."""
    args = ["ffmpeg", "-v", "error", "-y"]
    if start:
        args += ["-ss", f"{start:.2f}"]
    args += ["-i", str(src)]
    if length:
        args += ["-t", f"{length:.2f}"]
    args += ["-vn", "-ac", "1", "-ar", str(rate), "-c:a", "libopus", "-b:a", bitrate, str(out)]
    code, _, _ = await _run(*args, timeout=300)
    return out if code == 0 and out.exists() and out.stat().st_size > 0 else None


async def to_mp3(src: Path, out: Path) -> Path | None:
    """Audio track -> MP3 320 kbps."""
    code, _, _ = await _run("ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-c:a", "libmp3lame",
                            "-b:a", "320k", str(out), timeout=300)
    return out if code == 0 and out.exists() and out.stat().st_size > 1000 else None


async def to_wav(src: Path, out: Path, start: float, length: float) -> Path | None:
    """Mono 16 kHz WAV segment — the format Shazam signatures are computed from."""
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-i", str(src), "-t", f"{length:.2f}",
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out), timeout=120,
    )
    return out if code == 0 and out.exists() and out.stat().st_size > 1000 else None


FX = {
    # nightcore-style: faster and higher
    "up": lambda sr: f"asetrate={sr}*1.25,aresample={sr}",
    # slowed + reverb: slower, deeper, with a short multi-tap echo tail
    "slow": lambda sr: f"asetrate={sr}*0.85,aresample={sr},aecho=0.8:0.85:40|80|140:0.35|0.25|0.15",
}


async def make_fx(src: Path, out: Path, mode: str) -> Path | None:
    """Speed up / slowed + reverb version of a song as 320k MP3 (keeps the cover art)."""
    info = await probe(src)
    sr = info["sample_rate"] or 44100
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-map", "0:v?", "-c:v", "copy",
        "-af", FX[mode](sr), "-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3", str(out), timeout=300,
    )
    return out if code == 0 and out.exists() and out.stat().st_size > 0 else None


async def extract_cover(src: Path, out: Path) -> Path | None:
    """Cover art embedded in an MP3 -> Telegram-sized JPEG thumbnail."""
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-frames:v", "1",
        "-vf", "scale='if(gt(iw,ih),320,-2)':'if(gt(iw,ih),-2,320)'", "-q:v", "4", str(out), timeout=60,
    )
    return out if code == 0 and out.exists() and out.stat().st_size > 0 else None
