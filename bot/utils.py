import html
import re
import shutil
import time
from pathlib import Path

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

SUPPORTED_HOSTS = {
    "youtube": ("youtube.com", "youtu.be", "music.youtube.com", "youtube-nocookie.com"),
    "instagram": ("instagram.com", "instagr.am"),
    "tiktok": ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
}


def extract_url(text: str | None) -> str | None:
    if not text:
        return None
    m = URL_RE.search(text)
    return m.group(0).rstrip(").,!?»") if m else None


def detect_platform(url: str) -> str | None:
    host = re.sub(r"^https?://", "", url, flags=re.I).split("/")[0].split("?")[0].lower()
    host = host.split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    for platform, hosts in SUPPORTED_HOSTS.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return platform
    return None


def fmt_duration(seconds: float | int | None) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def esc(text: str | None) -> str:
    return html.escape(text or "", quote=False)


def clean_query(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:100]


def cleanup_old(dir_: Path, max_age: int = 3600) -> None:
    """Remove temp files / dirs older than max_age seconds."""
    if not dir_.exists():
        return
    now = time.time()
    for p in dir_.iterdir():
        try:
            if now - p.stat().st_mtime > max_age:
                shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
        except OSError:
            pass


_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})")


def canonical_key(url: str, platform: str) -> str:
    """Stable cache key for a link (so the same video is re-sent instantly)."""
    if platform == "youtube":
        m = _YT_ID.search(url)
        if m:
            return f"youtube:{m.group(1)}"
    base = re.sub(r"^https?://(www\.|m\.)?", "", url, flags=re.I).split("#")[0].split("?")[0].rstrip("/")
    return f"{platform}:{base.lower()}"
