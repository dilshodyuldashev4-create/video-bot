"""🔥 Top of the week (world), 🇺🇿 Uzbekistan and 🇷🇺 Russia charts — what is hot right now.

Sources, first that answers wins (all free, no keys), cached for a few hours:
1. Apple Music "most played" charts per country (weekly, with cover art);
2. Shazam charts (what people shazam, where TikTok / Reels hits show up first);
3. Deezer global chart (world only);
4. the newest YouTube uploads for the country's hits (sorted by upload date, not views,
   so years-old videos with many views don't fill the list).
"""
import asyncio
import datetime
import json
import logging
import time

from shazamio import Shazam

from . import downloader
from .mp3sites import http_get

log = logging.getLogger(__name__)

CACHE_TTL = 3 * 3600
LIMIT = 50
_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = asyncio.Lock()
_shazam = Shazam()

KINDS = ("world", "uz", "ru")


APPLE = "https://rss.applemarketingtools.com/api/v2/{country}/music/most-played/{limit}/songs.json"
APPLE_COUNTRY = {"world": "us", "uz": "uz", "ru": "ru"}
DEEZER_CHART = "https://api.deezer.com/chart/0/tracks?limit={limit}"
MIN_ITEMS = 10


def _item(artist: str, title: str, cover: str = "") -> dict:
    name = f"{artist} - {title}" if artist else title
    item = {"id": f"q:{name}"[:200], "title": name, "duration": 0}
    if cover:
        item["cover"] = cover
    return item


def parse_apple(data: dict) -> list[dict]:
    out = []
    for r in ((data or {}).get("feed") or {}).get("results") or []:
        if r.get("name"):
            cover = (r.get("artworkUrl100") or "").replace("100x100", "300x300")
            out.append(_item(r.get("artistName") or "", r["name"], cover))
    return out


def parse_deezer(data: dict) -> list[dict]:
    return [_item((r.get("artist") or {}).get("name") or "", r["title"], (r.get("album") or {}).get("cover_medium") or "")
            for r in (data or {}).get("data") or [] if r.get("title")]


async def _apple_chart(kind: str) -> list[dict]:
    url = APPLE.format(country=APPLE_COUNTRY[kind], limit=LIMIT)
    return parse_apple(json.loads(await asyncio.to_thread(http_get, url, "", 15)))


async def _deezer_chart(kind: str) -> list[dict]:
    if kind != "world":
        return []
    return parse_deezer(json.loads(await asyncio.to_thread(http_get, DEEZER_CHART.format(limit=LIMIT), "", 15)))


async def _shazam_chart(kind: str) -> list[dict]:
    if kind == "world":
        rows = await _shazam.top_world_tracks(limit=LIMIT)
    else:
        rows = await _shazam.top_country_tracks(kind.upper(), limit=LIMIT)
    return [_item(r.artist, r.title) for r in rows]


async def _youtube_hits(query: str) -> list[dict]:
    tracks = await downloader.search(query, limit=LIMIT, recent=True)
    return [{"id": tr.id, "title": downloader.clean_title(tr.title) or tr.title, "duration": tr.duration}
            for tr in tracks]


async def get_chart(kind: str) -> list[dict]:
    async with _lock:
        hit = _cache.get(kind)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    items: list[dict] = []
    for source in (_apple_chart, _shazam_chart, _deezer_chart):
        try:
            items = await asyncio.wait_for(source(kind), 30)
        except Exception as e:  # noqa: BLE001  (country not listed, network, format change)
            log.warning("chart %s from %s unavailable: %r", kind, source.__name__, e)
            items = []
        if len(items) >= MIN_ITEMS:
            log.info("chart %s from %s (%d)", kind, source.__name__, len(items))
            break
    if len(items) < MIN_ITEMS:
        now = datetime.date.today()
        fallback = {
            "world": f"new music {now:%B %Y} hits",
            "uz": f"yangi o'zbek qo'shiqlar {now.year}",
            "ru": f"новые русские хиты {now.year}",
        }[kind]
        items = await _youtube_hits(fallback) or items
    if items:
        async with _lock:
            _cache[kind] = (time.time(), items)
    return items
