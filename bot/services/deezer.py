"""Music metadata from the public Deezer API (no key): similar tracks and artists' new releases."""
import datetime
import json
import logging
import re
import urllib.parse

from .mp3sites import http_get

log = logging.getLogger(__name__)

API = "https://api.deezer.com"


def _get(path: str) -> dict:
    data = json.loads(http_get(API + path, timeout=15))
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"])[:120])
    return data


def _words(s: str) -> set[str]:
    return set(re.findall(r"\w{2,}", (s or "").lower().replace("ё", "е")))


def find_track(title: str, artist: str) -> dict | None:
    q = urllib.parse.quote(f"{artist} {title}".strip())
    rows = _get(f"/search?q={q}&limit=10").get("data") or []
    want_t, want_a = _words(title), _words(artist)
    for r in rows:
        if want_t & _words(r.get("title")) and (not want_a or want_a & _words((r.get("artist") or {}).get("name"))):
            return r
    return rows[0] if rows else None


def find_artist(name: str) -> dict | None:
    """{'id', 'name', 'picture'} of the best match."""
    q = urllib.parse.quote(name.strip())
    rows = _get(f"/search/artist?q={q}&limit=5").get("data") or []
    want = _words(name)
    for r in rows:
        if _words(r.get("name")) == want:
            break
    else:
        r = rows[0] if rows else None
    if not r:
        return None
    return {"id": str(r["id"]), "name": r.get("name") or name, "picture": r.get("picture_xl") or r.get("picture_big") or ""}


def _name(r: dict) -> str:
    artist = (r.get("artist") or {}).get("name") or ""
    return f"{artist} - {r.get('title') or ''}".strip(" -")


def similar(title: str, artist: str, limit: int = 30) -> list[str]:
    """'Artist - Title' of similar songs: the artist's radio (similar artists) first, then related artists' hits."""
    track = find_track(title, artist)
    if not track:
        return []
    aid = (track.get("artist") or {}).get("id")
    out: list[str] = []
    seen = {_name(track).lower()}

    def add(rows):
        for r in rows or []:
            n = _name(r)
            if n and n.lower() not in seen and len(out) < limit:
                seen.add(n.lower())
                out.append(n)

    if aid:
        try:
            add(_get(f"/artist/{aid}/radio?limit=40").get("data"))
        except Exception as e:  # noqa: BLE001
            log.info("deezer radio failed: %s", e)
        if len(out) < limit:
            for rel in (_get(f"/artist/{aid}/related?limit=8").get("data") or [])[:8]:
                add((_get(f"/artist/{rel['id']}/top?limit=3").get("data") or []))
    # don't fill the list with the same artist: at most 5 of theirs
    own = (track.get("artist") or {}).get("name", "").lower()
    mine = [n for n in out if n.lower().startswith(own + " - ")] if own else []
    return [n for n in out if n not in mine[5:]]


def latest_release(artist_id: str) -> dict | None:
    """Newest album / single: {'id', 'title', 'date', 'cover', 'type'}."""
    rows = _get(f"/artist/{artist_id}/albums?limit=50").get("data") or []
    rows = [r for r in rows if r.get("release_date")]
    if not rows:
        return None
    r = max(rows, key=lambda r: r["release_date"])
    return {"id": str(r["id"]), "title": r.get("title") or "", "date": r["release_date"],
            "cover": r.get("cover_xl") or r.get("cover_big") or "", "type": r.get("record_type") or "album"}


def is_fresh(date: str, days: int = 21) -> bool:
    try:
        d = datetime.date.fromisoformat(date[:10])
    except ValueError:
        return False
    return (datetime.date.today() - d).days <= days
