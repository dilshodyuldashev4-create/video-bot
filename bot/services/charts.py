"""🔥 Top of the week (world), 🇺🇿 Uzbekistan and 🇷🇺 Russia charts.

Source: Shazam charts (what people are shazaming right now, which is where TikTok/Reels
hits show up first). Charts are cached for a few hours. If Shazam has no chart for a
country (Uzbekistan is not always listed), the newest Uzbek hits are taken from YouTube.
"""
import asyncio
import datetime
import logging
import time

from shazamio import Shazam

from . import downloader

log = logging.getLogger(__name__)

CACHE_TTL = 3 * 3600
LIMIT = 50
_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = asyncio.Lock()
_shazam = Shazam()

KINDS = ("world", "uz", "ru")


def _item(artist: str, title: str) -> dict:
    name = f"{artist} - {title}" if artist else title
    return {"id": f"q:{name}"[:200], "title": name, "duration": 0}


async def _shazam_chart(kind: str) -> list[dict]:
    if kind == "world":
        rows = await _shazam.top_world_tracks(limit=LIMIT)
    else:
        rows = await _shazam.top_country_tracks(kind.upper(), limit=LIMIT)
    return [_item(r.artist, r.title) for r in rows]


async def _youtube_hits(query: str) -> list[dict]:
    tracks = await downloader.search(query, limit=LIMIT)
    return [{"id": tr.id, "title": downloader.clean_title(tr.title) or tr.title, "duration": tr.duration}
            for tr in tracks]


async def get_chart(kind: str) -> list[dict]:
    async with _lock:
        hit = _cache.get(kind)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    items: list[dict] = []
    try:
        items = await asyncio.wait_for(_shazam_chart(kind), 30)
    except Exception as e:  # noqa: BLE001  (country not listed, network, format change)
        log.warning("Shazam chart %s unavailable: %r", kind, e)
    if not items:
        year = datetime.date.today().year
        fallback = {
            "world": f"tiktok trending songs {year}",
            "uz": f"uzbek music hits {year}",
            "ru": f"русские хиты {year}",
        }[kind]
        items = await _youtube_hits(fallback)
    if items:
        async with _lock:
            _cache[kind] = (time.time(), items)
    return items
