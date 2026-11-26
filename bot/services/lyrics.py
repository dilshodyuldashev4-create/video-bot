"""Song lyrics from free sources, no API keys: LRCLIB, Genius pages, lyrics.ovh."""
import html
import json
import logging
import re
import urllib.parse
from html.parser import HTMLParser

from .mp3sites import http_get

log = logging.getLogger(__name__)

MAX_LEN = 12000


def _words(s: str) -> set[str]:
    return set(re.findall(r"\w{2,}", (s or "").lower().replace("ё", "е")))


def _matches(want_title: str, want_artist: str, title: str, artist: str) -> bool:
    wt, got = _words(want_title), _words(title)
    if not wt or len(wt & got) < max(1, (len(wt) + 1) // 2):
        return False
    wa = _words(want_artist)
    return not wa or bool(wa & (_words(artist) | got))


def clean(text: str) -> str:
    text = re.sub(r"\r", "", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_LEN]


def from_lrclib(title: str, artist: str) -> str | None:
    queries = [f"track_name={urllib.parse.quote(title)}" + (f"&artist_name={urllib.parse.quote(artist)}" if artist else ""),
               f"q={urllib.parse.quote(f'{artist} {title}'.strip())}"]
    for q in queries:
        rows = json.loads(http_get(f"https://lrclib.net/api/search?{q}", timeout=15))
        for r in rows or []:
            text = r.get("plainLyrics") or re.sub(r"\[\d+:\d+(?:\.\d+)?\]\s*", "", r.get("syncedLyrics") or "")
            if text.strip() and _matches(title, artist, r.get("trackName") or "", r.get("artistName") or ""):
                return clean(text)
    return None


class _GeniusLyrics(HTMLParser):
    """Collects text inside <div data-lyrics-container="true"> blocks (they nest other tags)."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth:
            if tag == "div":
                self.depth += 1
            if tag == "br":
                self.parts.append("\n")
            if a.get("data-exclude-from-selection") == "true":
                self.skip += 1
        elif tag == "div" and a.get("data-lyrics-container") == "true":
            self.depth = 1
            if self.parts:
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.depth and tag == "div":
            self.depth -= 1
            if self.skip:
                self.skip -= 1

    def handle_startendtag(self, tag, attrs):
        if self.depth and tag == "br":
            self.parts.append("\n")

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)


def parse_genius_page(page: str) -> str:
    p = _GeniusLyrics()
    p.feed(page)
    return clean(html.unescape("".join(p.parts)))


def from_genius(title: str, artist: str) -> str | None:
    q = urllib.parse.quote(f"{artist} {title}".strip())
    data = json.loads(http_get(f"https://genius.com/api/search/multi?q={q}", timeout=15))
    for section in (data.get("response") or {}).get("sections") or []:
        for hit in section.get("hits") or []:
            r = hit.get("result") or {}
            if hit.get("type") != "song" or not r.get("url"):
                continue
            if not _matches(title, artist, r.get("title") or "", (r.get("primary_artist") or {}).get("name") or ""):
                continue
            text = parse_genius_page(http_get(r["url"], timeout=20).decode("utf-8", "replace"))
            if text:
                return text
    return None


def from_lyrics_ovh(title: str, artist: str) -> str | None:
    if not artist:
        return None
    url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(artist)}/{urllib.parse.quote(title)}"
    text = json.loads(http_get(url, timeout=15)).get("lyrics") or ""
    return clean(text) if text.strip() else None


SOURCES = (from_lrclib, from_genius, from_lyrics_ovh)

_LRC = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


def parse_lrc(lrc: str) -> list[list]:
    """'[01:02.50] line' -> [[62.5, 'line'], ...], sorted by time (a line can carry several stamps)."""
    out = []
    for raw in (lrc or "").splitlines():
        stamps = _LRC.findall(raw)
        text = _LRC.sub("", raw).strip()
        for m, s in stamps:
            out.append([round(int(m) * 60 + float(s), 2), text])
    return sorted(out, key=lambda x: x[0])


def find_synced(title: str, artist: str) -> list[list] | None:
    """Time-stamped lyrics from LRCLIB for the karaoke view, or None. Blocking: run in a thread."""
    title = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", title).strip() or title
    q = f"track_name={urllib.parse.quote(title)}" + (f"&artist_name={urllib.parse.quote(artist)}" if artist else "")
    try:
        rows = json.loads(http_get(f"https://lrclib.net/api/search?{q}", timeout=15))
    except Exception as e:  # noqa: BLE001
        log.info("synced lyrics failed: %s", str(e)[:120])
        return None
    for r in rows or []:
        if r.get("syncedLyrics") and _matches(title, artist, r.get("trackName") or "", r.get("artistName") or ""):
            lines = parse_lrc(r["syncedLyrics"])
            if len(lines) >= 4:
                return lines
    return None


def find(title: str, artist: str) -> str | None:
    """Lyrics of a song, or None. Blocking: run in a thread."""
    title = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", title).strip() or title
    for source in SOURCES:
        try:
            if text := source(title, artist):
                log.info("lyrics for %s - %s from %s", artist, title, source.__name__)
                return text
        except Exception as e:  # noqa: BLE001
            log.info("lyrics source %s failed: %s", source.__name__, str(e)[:120])
    return None
