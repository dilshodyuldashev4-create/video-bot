"""Shared sending logic: MP3 tracks (with file_id cache) and per-user locks."""
import asyncio
import logging
import shutil
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, Message, ReactionTypeEmoji

from .db import DB
from .keyboards import audio_kb
from .services import downloader
from .texts import LINE, t
from .utils import esc

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


async def react(message: Message | None, emoji: str) -> None:
    """Put a reaction on the user's message (👀 working, 🔥 done, 😢 failed). Never fails."""
    if not message:
        return
    try:
        await message.react([ReactionTypeEmoji(emoji=emoji)])
    except Exception:  # reactions disabled in the chat, old message, etc.
        pass


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


def audio_caption(lang: str, username: str, title: str, performer: str, header: str | None = None) -> str:
    lines = [header] if header else []
    if title:
        lines.append(f"🎧 <b>{esc(title)}</b>")
    if performer:
        lines.append(f"👤 {esc(performer)}")
    lines += [LINE, t(lang, "audio_footer", bot=username)]
    return "\n".join(lines)


async def _send_cached(bot: Bot, db: DB, key: str, chat_id: int, lang: str, username: str,
                       header: str | None, reply_to: int | None) -> Message | None:
    cached = await db.get_file(key)
    if not cached:
        return None
    meta = cached[2]
    caption = audio_caption(lang, username, meta.get("title", ""), meta.get("performer", ""), header)
    try:
        return await bot.send_audio(chat_id, cached[1], caption=caption, reply_markup=audio_kb(username, lang),
                                    reply_to_message_id=reply_to)
    except TelegramBadRequest:
        await db.drop_file(key)
        return None


async def _send_fresh(bot: Bot, db: DB, key: str, chat_id: int, lang: str, username: str,
                      audio: downloader.AudioFile, header: str | None, reply_to: int | None) -> Message:
    caption = audio_caption(lang, username, audio.title, audio.performer, header)
    msg = await _upload_audio(bot, chat_id, audio, caption, audio_kb(username, lang), reply_to)
    if msg.audio:
        await db.put_file(key, "audio", msg.audio.file_id, {"title": audio.title, "performer": audio.performer})
    await db.incr("downloads")
    return msg


async def send_track(bot: Bot, db: DB, chat_id: int, video_id: str, lang: str,
                     header: str | None = None, reply_to: int | None = None, query: str = "") -> Message:
    """Send a YouTube track as MP3. Uses the cached Telegram file_id if we've sent it before.
    If YouTube refuses (blocked server IP etc.), the same song is taken from SoundCloud."""
    username = await bot_username(bot)
    key = f"a:{video_id}"
    if msg := await _send_cached(bot, db, key, chat_id, lang, username, header, reply_to):
        return msg
    try:
        audio = await downloader.download_audio(video_id)
    except downloader.DownloadFailed as e:
        if not query:
            raise
        log.warning("YouTube audio failed for %s, trying SoundCloud for %r: %s", video_id, query, str(e)[:200])
        audio = await downloader.download_audio_soundcloud(query)
    return await _send_fresh(bot, db, key, chat_id, lang, username, audio, header, reply_to)


async def send_soundcloud(bot: Bot, db: DB, chat_id: int, query: str, lang: str,
                          header: str | None = None, reply_to: int | None = None) -> Message:
    username = await bot_username(bot)
    key = f"sc:{query.lower()}"
    if msg := await _send_cached(bot, db, key, chat_id, lang, username, header, reply_to):
        return msg
    audio = await downloader.download_audio_soundcloud(query)
    return await _send_fresh(bot, db, key, chat_id, lang, username, audio, header, reply_to)
