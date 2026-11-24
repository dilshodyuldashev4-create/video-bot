"""MP3 catalogue sites (hitmotop and mirrors): full songs as plain MP3 files.

Used when YouTube blocks the server IP ("Sign in to confirm you're not a bot").
These sites have a huge catalogue of Uzbek / Russian / world pop, need no account and
serve ordinary MP3 links. Requests go through yt-dlp's HTTP stack, so the same
direct -> proxy (WARP) fallback is used as for everything else.
"""
import html
import json
import logging
import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import yt_dlp
from yt_dlp.networking import Request

from ..config import config

log = logging.getLogger(__name__)

# Mirrors are tried in order; HITMO_URL in .env overrides / adds one.
MIRRORS = [m for m in dict.fromkeys([
    os.getenv("HITMO_URL", "").strip().rstrip("/"),
    "https://rus.hitmotop.com",
    "https://eu.hitmotop.com",
    "https://hitmotop.com",
]) if m]

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
MIN_BYTES = 300 * 1024


@dataclass
class SiteTrack:
    artist: str
    title: str
    url: str
    cover: str = ""
    duration: int = 0


def _ydl(proxy: str | None) -> yt_dlp.YoutubeDL:
    opts = {"quiet": True, "no_warnings": True, "socket_timeout": 20}
    if proxy:
        opts["proxy"] = proxy
    return yt_dlp.YoutubeDL(opts)


def _get(url: str, referer: str = "") -> bytes:
    """GET with direct -> proxy fallback. Raises the last error."""
    headers = {"User-Agent": _UA, "Accept-Language": "ru,en;q=0.8"}
    if referer:
        headers["Referer"] = referer
    last: Exception | None = None
    for proxy in [None, config.proxy] if config.proxy else [None]:
        try:
            with _ydl(proxy) as ydl:
                with ydl.urlopen(Request(url, headers=headers)) as r:
                    return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            log.info("mp3site GET failed (%s) %s: %s", "proxy" if proxy else "direct", url[:120], str(e)[:160])
    assert last is not None
    raise last


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).strip()


def _duration(s: str) -> int:
    parts = [int(p) for p in re.findall(r"\d+", s)][-3:]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def parse_search(page: str, base: str) -> list[SiteTrack]:
    """Parse a hitmotop search page. Each track is an <li class="tracks__item ..."> with a
    data-musmeta JSON attribute; older layouts only have the title/desc/download-btn blocks."""
    tracks: list[SiteTrack] = []
    seen: set[str] = set()
    items = re.split(r'<li[^>]+class="[^"]*tracks__item', page)[1:]
    for item in items:
        artist = title = url = cover = ""
        m = re.search(r"data-musmeta=(['\"])(.*?)\1", item, re.S)
        if m:
            try:
                meta = json.loads(html.unescape(m.group(2)))
                artist, title = meta.get("artist") or "", meta.get("title") or ""
                url, cover = meta.get("url") or "", meta.get("img") or ""
            except ValueError:
                pass
        if not title:
            m = re.search(r'class="track__title"[^>]*>(.*?)</div>', item, re.S)
            title = _text(m.group(1)) if m else ""
        if not artist:
            m = re.search(r'class="track__desc"[^>]*>(.*?)</div>', item, re.S)
            artist = _text(m.group(1)) if m else ""
        m = re.search(r'href="([^"]+\.mp3[^"]*)"[^>]*class="[^"]*track__download-btn'
                      r'|class="[^"]*track__download-btn[^"]*"[^>]*href="([^"]+)"', item)
        if m:
            url = m.group(1) or m.group(2) or url
        if not url:
            m = re.search(r'(https?://[^"\'\s]+\.mp3)', item)
            url = m.group(1) if m else ""
        if not url or not title:
            continue
        url = urllib.parse.urljoin(base + "/", html.unescape(url))
        if url in seen:
            continue
        seen.add(url)
        m = re.search(r'class="track__fulltime"[^>]*>(.*?)</div>', item, re.S)
        tracks.append(SiteTrack(artist=artist.strip(), title=title.strip(), url=url,
                                cover=urllib.parse.urljoin(base + "/", cover) if cover else "",
                                duration=_duration(_text(m.group(1))) if m else 0))
    return tracks


def search_sync(query: str) -> tuple[list[SiteTrack], str]:
    last: Exception | None = None
    for base in MIRRORS:
        try:
            page = _get(f"{base}/search?q={urllib.parse.quote_plus(query)}", referer=base + "/")
        except Exception as e:  # noqa: BLE001
            last = e
            continue
        return parse_search(page.decode("utf-8", "replace"), base), base
    raise RuntimeError(f"all mp3 mirrors failed: {last}")


def _words(s: str) -> set[str]:
    return set(re.findall(r"\w{2,}", s.lower()))


def pick(tracks: list[SiteTrack], title: str, artist: str) -> list[SiteTrack]:
    """Tracks whose title really matches, best first (artist match, no remixes)."""
    from .downloader import similarity  # local import: downloader imports this module

    want_title, want_artist = _words(title), _words(artist)
    query = f"{artist} - {title}" if artist else title
    good = []
    for t in tracks:
        tw = _words(t.title)
        if want_title and len(want_title & tw) < max(1, (len(want_title) + 1) // 2):
            continue
        s = similarity(query, f"{t.artist} - {t.title}")
        if want_artist and want_artist & _words(t.artist):
            s += 0.5
        if any(w in t.title.lower() for w in ("remix", "cover", "slowed", "speed up", "sped up", "karaoke")) \
                and not any(w in query.lower() for w in ("remix", "cover", "slowed", "speed")):
            s -= 0.3
        good.append((s, t))
    return [t for _, t in sorted(good, key=lambda x: x[0], reverse=True)]


def download_sync(track: SiteTrack, referer: str, workdir: Path) -> tuple[Path, Path | None]:
    data = _get(track.url, referer=referer)
    if len(data) < MIN_BYTES or not (data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        raise RuntimeError(f"not an mp3 ({len(data)} bytes)")
    path = workdir / "song.mp3"
    path.write_bytes(data)
    cover = None
    if track.cover:
        try:
            img = _get(track.cover, referer=referer)
            if len(img) > 1000:
                cover = workdir / "cover.jpg"
                cover.write_bytes(img)
        except Exception:  # noqa: BLE001
            pass
    return path, cover
