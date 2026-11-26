"""🌊 The personal stream ("Мой поток") and genre streams for the Mini App.

The player tells the bot what each user plays, finishes and skips (db.listens); likes and the
tracks the bot sent count too. From that we take the user's favourite artists, and for each one
Deezer's "artist radio" (songs of similar artists). That is mixed with fresh charts and the
user's own likes, skipped songs are dropped, and the same artist never plays twice in a row.

Genres: Deezer's chart per genre (with covers), or a YouTube search for genres Deezer does not
cover (Uzbek pop, phonk...). A genre stream puts the user's own artists from that genre first.
"""
import asyncio
import datetime
import json
import logging
import random
import re
import time
import urllib.parse

from . import charts, downloader
from .mp3sites import http_get

log = logging.getLogger(__name__)

API = "https://api.deezer.com"
TTL = 6 * 3600
WAVE_SIZE = 60
_cache: dict[str, tuple[float, object]] = {}

# key -> (Deezer genre id or None, YouTube query when there is no Deezer genre)
GENRES: dict[str, tuple[int | None, str]] = {
    "uzpop": (None, "yangi o'zbek qo'shiqlar {y}"),
    "pop": (132, ""),
    "hiphop": (116, ""),
    "rnb": (165, ""),
    "dance": (113, ""),
    "electro": (106, ""),
    "phonk": (None, "phonk {y}"),
    "rock": (152, ""),
    "lofi": (None, "lofi hip hop chill"),
    "latin": (197, ""),
    "jazz": (129, ""),
    "classical": (98, ""),
}


def _get(path: str) -> dict:
    data = json.loads(http_get(API + path, timeout=15))
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"])[:120])
    return data


def _rows(rows) -> list[dict]:
    out = []
    for r in rows or []:
        if r.get("title"):
            out.append(charts._item((r.get("artist") or {}).get("name") or "", r["title"],
                                    (r.get("album") or {}).get("cover_medium") or ""))
    return out


async def _cached(key: str, make):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    value = await make()
    if value:
        _cache[key] = (time.time(), value)
    return value


def _norm(s: str) -> str:
    return re.sub(r"\W+", "", (s or "").lower())


async def _youtube(query: str, uzbek: bool = False) -> list[dict]:
    tracks = await downloader.search(query.format(y=datetime.date.today().year), limit=40)
    out = []
    for tr in tracks:
        title = downloader.clean_title(tr.title) or tr.title
        if 90 <= (tr.duration or 0) <= 480 and not charts.COMPILATION.search(tr.title) \
                and (not uzbek or charts.is_uzbek(title)):
            out.append({"id": tr.id, "title": title, "duration": tr.duration})
    return out


async def genre_tracks(key: str) -> list[dict]:
    """Top songs of a genre, cached for a few hours."""
    gid, query = GENRES[key]

    async def make():
        if gid is not None:
            try:
                return _rows((await asyncio.to_thread(_get, f"/chart/{gid}/tracks?limit=50")).get("data"))
            except Exception as e:  # noqa: BLE001
                log.warning("genre %s from Deezer failed: %r", key, e)
                return []
        return await _youtube(query, uzbek=key == "uzpop")

    return await _cached("g:" + key, make)


async def artist_radio(name: str) -> list[dict]:
    """Songs like this artist's: Deezer artist radio; YouTube when Deezer doesn't know them."""
    async def make():
        try:
            q = urllib.parse.quote(name)
            rows = (await asyncio.to_thread(_get, f"/search/artist?q={q}&limit=5")).get("data") or []
            match = next((r for r in rows if _norm(r.get("name")) == _norm(name)), None)
            if match:
                return _rows((await asyncio.to_thread(_get, f"/artist/{match['id']}/radio?limit=25")).get("data"))
        except Exception as e:  # noqa: BLE001
            log.info("artist radio %s failed: %r", name, e)
        tracks = await _youtube(f"{name} {{y}}")
        return [t for t in tracks if _norm(name) in _norm(t["title"])][:12]

    return await _cached("a:" + name.lower(), make)


def _spread(items: list[dict], limit: int, per_artist: int = 3) -> list[dict]:
    """No artist twice in a row, at most `per_artist` songs each."""
    pool, out, count = list(items), [], {}
    while pool and len(out) < limit:
        last = out[-1]["title"].partition(" - ")[0].lower() if out else None
        for i, it in enumerate(pool):
            a = it["title"].partition(" - ")[0].lower()
            if a != last or len(pool) == 1:
                pool.pop(i)
                if count.get(a, 0) < per_artist:
                    count[a] = count.get(a, 0) + 1
                    out.append(it)
                break
        else:
            break
    return out


async def build(taste: dict, likes: list[dict], genre: str | None = None, limit: int = WAVE_SIZE) -> dict:
    """{'items': [...], 'seeds': [artist names it was built from]}."""
    top = [a for a, _ in taste.get("artists", [])]
    blocked = set(taste.get("skipped", set())) | set(taste.get("recent", set()))
    picked: list[dict] = []

    if genre:
        base = await genre_tracks(genre)
        in_genre = {it["title"].partition(" - ")[0].lower() for it in base}
        seeds = [a for a in top if a.lower() in in_genre][:3] or \
            [it["title"].partition(" - ")[0] for it in base[:3]]
        radios = await asyncio.gather(*(artist_radio(a) for a in seeds), return_exceptions=True)
        personal = [it for r in radios if isinstance(r, list) for it in r]
        random.shuffle(personal)
        rest = list(base)
        random.shuffle(rest)
        picked = [x for pair in zip(personal, rest) for x in pair] + personal[len(rest):] + rest[len(personal):]
    else:
        seeds = top[:6]
        radios = await asyncio.gather(*(artist_radio(a) for a in seeds), return_exceptions=True)
        personal = [it for r in radios if isinstance(r, list) for it in r]
        fresh = []
        for kind in ("uz", "world"):
            try:
                fresh += (await asyncio.wait_for(charts.get_chart(kind), 40))[:25]
            except Exception as e:  # noqa: BLE001
                log.info("wave chart %s failed: %r", kind, e)
        random.shuffle(personal)
        random.shuffle(fresh)
        own = random.sample(likes, min(len(likes), 12))
        # mostly new songs like the ones you love, some fresh hits, a few of your own likes
        while personal or fresh or own:
            for src, n in ((personal, 3), (fresh, 1), (own, 1)):
                picked += [src.pop() for _ in range(min(n, len(src)))]

    seen, out = set(), []
    for it in picked:
        key = it["title"].lower()
        if key in blocked or _norm(key) in seen:
            continue
        seen.add(_norm(key))
        out.append(it)
    return {"items": _spread(out, limit), "seeds": seeds[:5]}
