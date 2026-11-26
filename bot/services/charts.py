"""🔥 Top of the week (world), 🇺🇿 Uzbekistan and 🇷🇺 Russia charts — what is hot right now.
The 🇺🇿 chart holds Uzbek songs only (see _uz_chart).

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
import re
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


# ---------------------------------------------------------------- Uzbekistan: Uzbek songs only
# Apple / Shazam "Uzbekistan" charts are what people in the country play, and that is mostly
# Russian and Turkish pop. The 🇺🇿 tab keeps only the Uzbek songs from them and fills up
# with this year's Uzbek hits from YouTube.
UZ_ARTISTS = (
    "shahzoda", "ozoda", "jaloliddin ahmadov", "konsta", "ummon", "xamdam sobirov", "hamdam sobirov",
    "shohruhxon", "shoxruxxon", "lola yuldasheva", "rayhon", "yulduz usmonova", "sevara nazarxon",
    "sardor rahimxon", "munisa rizayeva", "bojalar", "jahongir otajonov", "dildora niyozova",
    "ulug'bek rahmatullayev", "ulugbek rahmatullayev", "asl wayne", "lali", "benom", "yalla",
    "ziyoda", "kanizaki", "jasur umirov", "alisher fayz", "sherali jo'rayev", "ozodbek nazarbekov",
    "nilufar usmonova", "farrux xamrayev", "afruza", "madina aknazarova", "shaxriyor", "shahriyor",
    "doston ergashev", "bunyod", "manzura", "sardor mamadaliyev", "xurshid rasulov", "real bek",
    "sarvar", "fayzulla", "ilhom", "mirjalol nematov", "muxlisa", "gulsanam", "ruxshona", "nasiba",
    "ozodbek", "jasurbek", "shoxjahon", "ulug'bek", "otabek mutalxo'jayev", "zarina", "mohito",
)
UZ_WORDS = {
    "sevgi", "sevgim", "sevgilim", "sevaman", "sevdim", "yorim", "yorginam", "jonim", "jonginam", "qiz", "qizim",
    "qizlar", "onam", "onajon", "onajonim", "otam", "dunyo", "bahor", "yurak", "yuragim", "nega", "qayt", "qaytma",
    "ketma", "kelmadi", "ayriliq", "armon", "armonim", "xayr", "seni", "meni", "sensiz", "mensiz", "sog'indim",
    "sogindim", "baxt", "baxtim", "taqdir", "muhabbat", "oshiq", "oshiqman", "yig'lama", "yiglama", "dilim",
    "dildor", "kechir", "kechirgin", "yolg'iz", "yolgiz", "chiroyli", "qo'shiq", "qoshiq", "to'y", "toy",
    "kuyov", "kelin", "dugona", "jo'ra", "jora", "ko'zlar", "kozlar", "go'zal", "gozal", "yaxshi", "yomon",
    "bolajon", "o'zbek", "ozbek", "uzbek", "o'zbekiston", "uzbekistan", "toshkent", "samarqand", "andijon",
}
NOT_UZ = re.compile(r"[ıçşğ]")          # Turkish / Azeri letters
UZ_LETTERS = re.compile(r"[ўқғҳ]|\b[og]['ʻ’‘`]\w")
COMPILATION = re.compile(r"\b(mix|to'?plam|jamlanma|top ?\d+|konsert|concert|playlist|remixes|non ?stop|"
                         r"hits? \d{4}|xitlar|qo'?shiqlar)\b", re.I)


def is_uzbek(title: str) -> bool:
    low = title.lower()
    if NOT_UZ.search(low):
        return False
    if UZ_LETTERS.search(low):
        return True
    artist = low.partition(" - ")[0]
    if any(re.search(rf"(?<!\w){re.escape(a)}(?!\w)", artist) for a in UZ_ARTISTS):
        return True
    return bool(set(re.findall(r"[a-z']+", low)) & UZ_WORDS)


def _uz_queries() -> list[str]:
    y = datetime.date.today().year
    return [f"o'zbek xit qo'shiqlar {y}", f"yangi o'zbek qo'shiqlar {y}", f"uzbek music {y} official video",
            f"premyera {y} o'zbek klip"]


async def _uz_youtube() -> list[dict]:
    """This year's Uzbek songs from YouTube: popular ones first, one song per video, no hour-long mixes."""
    found = await asyncio.gather(*(downloader.search(q, limit=40) for q in _uz_queries()), return_exceptions=True)
    out = []
    for tracks in found:
        if isinstance(tracks, BaseException):
            log.warning("uz chart search failed: %r", tracks)
            continue
        for tr in tracks:
            title = downloader.clean_title(tr.title) or tr.title
            if 90 <= (tr.duration or 0) <= 480 and not COMPILATION.search(tr.title) and is_uzbek(title):
                out.append({"id": tr.id, "title": title, "duration": tr.duration})
    return out


async def _uz_chart() -> list[dict]:
    items: list[dict] = []
    for source in (_apple_chart, _shazam_chart):
        try:
            items += [it for it in await asyncio.wait_for(source("uz"), 30) if is_uzbek(it["title"])]
        except Exception as e:  # noqa: BLE001
            log.warning("chart uz from %s unavailable: %r", source.__name__, e)
    if len(items) < LIMIT:
        items += await _uz_youtube()
    seen, out = set(), []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out[:LIMIT]


async def get_chart(kind: str) -> list[dict]:
    async with _lock:
        hit = _cache.get(kind)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    items: list[dict] = []
    sources = () if kind == "uz" else (_apple_chart, _shazam_chart, _deezer_chart)
    if kind == "uz":
        items = await _uz_chart()
    for source in sources:
        try:
            items = await asyncio.wait_for(source(kind), 30)
        except Exception as e:  # noqa: BLE001  (country not listed, network, format change)
            log.warning("chart %s from %s unavailable: %r", kind, source.__name__, e)
            items = []
        if len(items) >= MIN_ITEMS:
            log.info("chart %s from %s (%d)", kind, source.__name__, len(items))
            break
    if len(items) < MIN_ITEMS and not (kind == "uz" and items):
        now = datetime.date.today()
        fallback = {
            "world": f"new music {now:%B %Y} hits",
            "uz": f"yangi o'zbek qo'shiqlar {now.year}",
            "ru": f"новые русские хиты {now.year}",
        }[kind]
        hits = await _youtube_hits(fallback)
        if kind == "uz":
            hits = [it for it in hits if is_uzbek(it["title"])]
        items = hits or items
    if items:
        async with _lock:
            _cache[kind] = (time.time(), items)
    return items
