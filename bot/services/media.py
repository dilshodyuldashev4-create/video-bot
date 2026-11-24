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
    # 8D audio: the sound slowly circles around the head (best with headphones)
    "8d": lambda sr: "apulsator=hz=0.08:amount=0.9,aecho=0.8:0.6:25:0.12,alimiter=limit=0.95",
    # bass boost
    "bass": lambda sr: "bass=g=9:f=100:w=0.6,alimiter=limit=0.95",
}

# Karaoke / minus: vocals are usually mixed in the centre, so left minus right removes them;
# the bass (also centred) is put back from a low-passed copy so the beat stays full.
MINUS_FILTER = ("[0:a]asplit=2[a][b];[a]pan=stereo|c0=c0-c1|c1=c1-c0[side];"
                "[b]lowpass=f=160,pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1[bass];"
                "[side][bass]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]")


async def make_fx(src: Path, out: Path, mode: str) -> Path | None:
    """Speed up / slowed + reverb version of a song as 320k MP3 (keeps the cover art)."""
    info = await probe(src)
    sr = info["sample_rate"] or 44100
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-map", "0:v?", "-c:v", "copy",
        "-af", FX[mode](sr), "-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3", str(out), timeout=300,
    )
    return out if code == 0 and out.exists() and out.stat().st_size > 0 else None


async def is_stereo(src: Path) -> bool:
    code, out, _ = await _run("ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                              "stream=channels", "-of", "csv=p=0", str(src), timeout=30)
    try:
        return code == 0 and int((out or b"0").decode().strip().split(",")[0] or 0) >= 2
    except ValueError:
        return False


async def make_minus(src: Path, out: Path) -> Path | None:
    """Instrumental (karaoke) version: vocals removed with phase cancellation (fast, CPU only)."""
    if not await is_stereo(src):
        return None
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", MINUS_FILTER, "-map", "[out]",
        "-map", "0:v?", "-c:v", "copy", "-c:a", "libmp3lame", "-b:a", "320k", "-id3v2_version", "3", str(out),
        timeout=300,
    )
    return out if code == 0 and out.exists() and out.stat().st_size > 1000 else None


RINGTONE_SECONDS = 30


async def best_part(src: Path, length: float = RINGTONE_SECONDS) -> float:
    """Start of the loudest `length` seconds (usually the chorus), found from 1 s RMS levels."""
    info = await probe(src)
    dur = info["duration"]
    if dur <= length + 2:
        return 0.0
    code, _, err = await _run(
        "ffmpeg", "-v", "info", "-i", str(src), "-vn",
        "-af", "aformat=channel_layouts=mono,aresample=8000,asetnsamples=n=8000,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
        "-f", "null", "-", timeout=120)
    levels = []
    for line in (err or b"").decode("utf-8", "replace").splitlines():
        if "RMS_level=" in line:
            try:
                v = float(line.rsplit("=", 1)[1])
            except ValueError:
                v = -90.0
            levels.append(v if v > -90 else -90.0)
    n = int(length)
    if code != 0 or len(levels) <= n:
        return round(dur * 0.3, 1)
    # skip intro / outro, prefer the loudest window
    lo, hi = int(len(levels) * 0.1), max(int(len(levels) * 0.85) - n, int(len(levels) * 0.1) + 1)
    best, best_sum = lo, None
    window = sum(levels[lo:lo + n])
    for i in range(lo, hi):
        if i > lo:
            window += levels[i + n - 1] - levels[i - 1]
        if best_sum is None or window > best_sum:
            best, best_sum = i, window
    return float(min(best, max(0.0, dur - length)))


async def make_ringtone(src: Path, workdir: Path, name: str) -> tuple[Path | None, Path | None]:
    """30 s from the best part: iPhone .m4r (AAC) and Android .mp3, with short fades."""
    start = await best_part(src)
    fade = f"afade=t=in:d=1,afade=t=out:st={RINGTONE_SECONDS - 1.5}:d=1.5"
    m4r, mp3 = workdir / f"{name}.m4r", workdir / f"{name}.mp3"
    common = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.1f}", "-t", str(RINGTONE_SECONDS), "-i", str(src),
              "-vn", "-af", fade]
    c1, _, _ = await _run(*common, "-c:a", "aac", "-b:a", "192k", "-f", "ipod", str(m4r), timeout=120)
    c2, _, _ = await _run(*common, "-c:a", "libmp3lame", "-b:a", "256k", str(mp3), timeout=120)
    return (m4r if c1 == 0 and m4r.exists() else None), (mp3 if c2 == 0 and mp3.exists() else None)


async def to_video_note(src: Path, out: Path) -> Path | None:
    """Telegram "кружок": square, centre-cropped, up to 60 s, 512 px."""
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", "59.5",
        "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=512:512,setsar=1,fps=30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out), timeout=300)
    return out if code == 0 and out.exists() and out.stat().st_size > 1000 else None


async def to_voice(src: Path, out: Path) -> Path | None:
    """Telegram voice message: OGG/Opus mono, up to 10 minutes."""
    code, _, _ = await _run("ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", "600", "-vn", "-ac", "1",
                            "-ar", "48000", "-c:a", "libopus", "-b:a", "64k", str(out), timeout=300)
    return out if code == 0 and out.exists() and out.stat().st_size > 100 else None


async def extract_cover(src: Path, out: Path) -> Path | None:
    """Cover art embedded in an MP3 -> Telegram-sized JPEG thumbnail."""
    code, _, _ = await _run(
        "ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-frames:v", "1",
        "-vf", "scale='if(gt(iw,ih),320,-2)':'if(gt(iw,ih),-2,320)'", "-q:v", "4", str(out), timeout=60,
    )
    return out if code == 0 and out.exists() and out.stat().st_size > 0 else None
