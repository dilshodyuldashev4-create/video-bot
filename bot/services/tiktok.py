"""TikTok through the public tikwm.com API: no-watermark video (HD when available),
photo slideshows and the original sound. Used when yt-dlp can't get TikTok formats
("No video formats found!" happens when TikTok changes its pages or blocks the server)."""
import json
import logging
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .mp3sites import http_get

log = logging.getLogger(__name__)

API = "https://www.tikwm.com/api/?hd=1&url="
BASE = "https://www.tikwm.com/"
MIN_BYTES = 20 * 1024


@dataclass
class TikTokPost:
    id: str
    title: str
    author: str
    duration: int
    video: str = ""
    images: list[str] = field(default_factory=list)
    music: str = ""
    music_title: str = ""
    music_author: str = ""
    cover: str = ""


def _abs(u: str) -> str:
    return urllib.parse.urljoin(BASE, u) if u else ""


def parse(data: dict) -> TikTokPost:
    if data.get("code") != 0 or not data.get("data"):
        raise RuntimeError(f"tikwm: {data.get('msg') or 'no data'}")
    d = data["data"]
    music = d.get("music_info") or {}
    return TikTokPost(
        id=str(d.get("id") or ""), title=d.get("title") or "",
        author=(d.get("author") or {}).get("nickname") or "",
        duration=int(d.get("duration") or 0),
        video=_abs(d.get("hdplay") or d.get("play") or ""),
        images=[_abs(u) for u in d.get("images") or []],
        music=_abs(d.get("music") or music.get("play") or ""),
        music_title=music.get("title") or "", music_author=music.get("author") or "",
        cover=_abs(d.get("cover") or ""),
    )


def fetch(url: str) -> TikTokPost:
    return parse(json.loads(http_get(API + urllib.parse.quote(url, safe=""), timeout=20)))


def download(url: str, workdir: Path, limit: int) -> TikTokPost:
    """Video (or slideshow photos) of a TikTok post into workdir."""
    post = fetch(url)
    if post.images:
        for i, img in enumerate(post.images[:10]):
            (workdir / f"{post.id}_{i:02d}.jpg").write_bytes(http_get(img, timeout=30))
        return post
    if not post.video:
        raise RuntimeError("tikwm: no video url")
    data = http_get(post.video, referer=BASE, timeout=120)
    if len(data) < MIN_BYTES:
        raise RuntimeError(f"tikwm: video too small ({len(data)} bytes)")
    if len(data) > limit:
        raise OverflowError("too big")
    (workdir / f"{post.id or 'tiktok'}.mp4").write_bytes(data)
    return post
