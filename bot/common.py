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


async def send_track(bot: Bot, db: DB, chat_id: int, video_id: str, lang: str,
                     caption: str | None = None, reply_to: int | None = None) -> Message:
    """Send a YouTube track as MP3. Uses the cached Telegram file_id if we've sent it before."""
    username = await bot_username(bot)
    caption = caption or t(lang, "audio_caption", bot=username)
    kb = audio_kb(username, lang)
    key = f"a:{video_id}"
    cached = await db.get_file(key)
    if cached:
        try:
            return await bot.send_audio(chat_id, cached[1], caption=caption, reply_markup=kb,
                                        reply_to_message_id=reply_to)
        except TelegramBadRequest:
            await db.drop_file(key)

    audio = await downloader.download_audio(video_id)
    try:
        msg = await bot.send_audio(
            chat_id,
            FSInputFile(audio.path, filename=f"{audio.performer} - {audio.title}.mp3"[:120]),
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
    if msg.audio:
        await db.put_file(key, "audio", msg.audio.file_id, {"title": audio.title, "performer": audio.performer})
    await db.incr("downloads")
    return msg
