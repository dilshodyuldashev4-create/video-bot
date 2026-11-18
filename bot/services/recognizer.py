"""Shazam-style music recognition (via the shazamio library)."""
import asyncio
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from shazamio import Shazam

from ..config import config
from . import media

log = logging.getLogger(__name__)

SEGMENT = 12.0  # seconds per attempt; Shazam needs ~5-12 s
_shazam = Shazam()
_sem = asyncio.Semaphore(4)


@dataclass
class Song:
    title: str
    artist: str
    cover: str | None = None
    shazam_url: str | None = None

    @property
    def query(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title


def segment_offsets(duration: float) -> list[float]:
    """Where to listen. Speech is common at the start of reels, so the middle goes first,
    then the start, then later parts. Short clips are listened to as a whole."""
    if duration <= SEGMENT + 3:
        return [0.0]
    last = max(0.0, duration - SEGMENT)
    picks = [duration * 0.4, 0.0, duration * 0.7, duration * 0.15, last]
    out: list[float] = []
    for p in picks:
        p = round(min(max(0.0, p - SEGMENT / 2 if p else 0.0), last), 1)
        if all(abs(p - q) > SEGMENT / 2 for q in out):
            out.append(p)
    return out


def _parse(result: dict) -> Song | None:
    track = (result or {}).get("track")
    if not track or not track.get("title"):
        return None
    images = track.get("images") or {}
    return Song(
        title=track["title"].strip(),
        artist=(track.get("subtitle") or "").strip(),
        cover=images.get("coverarthq") or images.get("coverart"),
        shazam_url=track.get("url"),
    )


async def _recognize_file(path: Path) -> Song | None:
    async with _sem:
        try:
            result = await asyncio.wait_for(_shazam.recognize(str(path)), 30)
        except Exception as e:  # network hiccups, rate limits, decode errors
            log.warning("shazam error on %s: %r", path.name, e)
            await asyncio.sleep(1)
            try:
                result = await asyncio.wait_for(_shazam.recognize(str(path)), 30)
            except Exception:
                return None
    return _parse(result)


async def recognize(src: Path, max_attempts: int = 5) -> Song | None:
    """Recognise music in any audio/video file."""
    info = await media.probe(src)
    if not info["has_audio"]:
        return None
    work = config.tmp_dir / f"rec_{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        for i, off in enumerate(segment_offsets(info["duration"])[:max_attempts]):
            wav = await media.to_wav(src, work / f"seg{i}.wav", off, SEGMENT)
            if not wav:
                continue
            song = await _recognize_file(wav)
            if song:
                log.info("recognised %s at %.1fs", song.query, off)
                return song
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
