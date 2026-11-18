"""Shared sending logic: MP3 tracks (with file_id cache) and per-user locks."""
import asyncio
import logging
import shutil
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, Message

from .db import DB
from .keyboards import audio_kb
from .services import downloader
from .texts import t

log = logging.getLogger(__name__)

_locks: dict[int, asyncio.Lock] = {}


@asynccontextmanager
async def user_lock(user_id: int):
    """Yields False if the user already has a job running (no queue spam)."""
    lock = _locks.setdefault(user_id, asyncio.Lock())
    if lock.locked():
        yield False
        return
    async with lock:
        yield True


async def bot_username(bot: Bot) -> str:
    if not getattr(bot, "_cached_username", None):
        bot._cached_username = (await bot.me()).username
    return bot._cached_username


async def _upload_audio(bot: Bot, chat_id: int, audio: downloader.AudioFile, caption: str, kb,
                        reply_to: int | None) -> Message:
    try:
        return await bot.send_audio(
            chat_id,
            FSInputFile(audio.path, filename=f"{audio.performer} - {audio.title}.mp3".strip(" -")[:120]),
            title=audio.title[:64] or None,
            performer=audio.performer[:64] or None,
            duration=audio.duration or None,
            thumbnail=FSInputFile(audio.thumb) if audio.thumb else None,
            caption=caption,
            reply_markup=kb,
            reply_to_message_id=reply_to,
            request_timeout=600,
        )
    finally:
        shutil.rmtree(audio.path.parent, ignore_errors=True)


async def _send_cached(bot: Bot, db: DB, key: str, chat_id: int, caption: str, kb,
                       reply_to: int | None) -> Message | None:
    cached = await db.get_file(key)
    if not cached:
        return None
    try:
        return await bot.send_audio(chat_id, cached[1], caption=caption, reply_markup=kb,
                                    reply_to_message_id=reply_to)
    except TelegramBadRequest:
        await db.drop_file(key)
        return None


async def send_track(bot: Bot, db: DB, chat_id: int, video_id: str, lang: str,
                     caption: str | None = None, reply_to: int | None = None, query: str = "") -> Message:
    """Send a YouTube track as MP3. Uses the cached Telegram file_id if we've sent it before.
    If YouTube refuses (blocked server IP etc.), the same song is taken from SoundCloud."""
    username = await bot_username(bot)
    caption = caption or t(lang, "audio_caption", bot=username)
    kb = audio_kb(username, lang)
    key = f"a:{video_id}"
    if msg := await _send_cached(bot, db, key, chat_id, caption, kb, reply_to):
        return msg
    try:
        audio = await downloader.download_audio(video_id)
    except downloader.DownloadFailed as e:
        if not query:
            raise
        log.warning("YouTube audio failed for %s, trying SoundCloud for %r: %s", video_id, query, str(e)[:200])
        audio = await downloader.download_audio_soundcloud(query)
    msg = await _upload_audio(bot, chat_id, audio, caption, kb, reply_to)
    if msg.audio:
        await db.put_file(key, "audio", msg.audio.file_id, {"title": audio.title, "performer": audio.performer})
    await db.incr("downloads")
    return msg


async def send_soundcloud(bot: Bot, db: DB, chat_id: int, query: str, lang: str,
                          caption: str | None = None, reply_to: int | None = None) -> Message:
    username = await bot_username(bot)
    caption = caption or t(lang, "audio_caption", bot=username)
    kb = audio_kb(username, lang)
    key = f"sc:{query.lower()}"
    if msg := await _send_cached(bot, db, key, chat_id, caption, kb, reply_to):
        return msg
    audio = await downloader.download_audio_soundcloud(query)
    msg = await _upload_audio(bot, chat_id, audio, caption, kb, reply_to)
    if msg.audio:
        await db.put_file(key, "audio", msg.audio.file_id, {"title": audio.title, "performer": audio.performer})
    await db.incr("downloads")
    return msg
