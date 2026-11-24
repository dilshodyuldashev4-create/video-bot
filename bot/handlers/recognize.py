"""Shazam: video / audio / voice / video note -> song name -> MP3."""
import logging
import shutil
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from ..common import react, send_song, user_lock
from ..config import config
from ..db import DB
from ..services import downloader, recognizer
from ..services.recognizer import Song
from ..texts import t
from ..utils import esc
from .links import clips_dir

log = logging.getLogger(__name__)
router = Router(name="recognize")

MEDIA = F.video | F.audio | F.voice | F.video_note | (
    F.document & F.document.mime_type.regexp(r"^(audio|video)/")
)


def _file_of(message: Message):
    return message.video or message.audio or message.voice or message.video_note or message.document


async def _fetch(bot: Bot, file_id: str, size: int | None) -> Path | None:
    """Download a Telegram file to a temp dir. None if too large for the Bot API."""
    if size and size > config.download_limit:
        return None
    work = config.tmp_dir / f"in_{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    dest = work / "input"
    try:
        await bot.download(file_id, destination=dest, timeout=600)
    except TelegramBadRequest as e:  # "file is too big"
        log.warning("cannot fetch file: %s", e)
        shutil.rmtree(work, ignore_errors=True)
        return None
    return dest


async def _deliver(message: Message, bot: Bot, db: DB, lang: str, song: Song | None, hint: str = "") -> bool:
    """Send the recognised song as an MP3 (or say we couldn't recognise it)."""
    if not song and hint:
        artist, _, title = hint.partition(" - ")
        song = Song(title=title or hint, artist=artist if title else "")
    if not song:
        await message.reply(t(lang, "not_recognized"))
        return False
    await db.incr("recognitions")
    card_text = t(lang, "recognized_card", title=esc(song.title), artist=esc(song.artist))
    card = await _send_card(message, song, card_text, lang)
    header = t(lang, "recognized_header")
    try:
        await send_song(bot, db, message.chat.id, song.title, song.artist, lang, header, message.message_id)
    except downloader.DownloadFailed:
        await message.reply(t(lang, "song_not_found_dl", title=esc(song.title), artist=esc(song.artist)))
    finally:
        await _finish_card(card, card_text)
    return True


async def _send_card(message: Message, song: Song, text: str, lang: str) -> Message | None:
    """Shazam-style card: cover art + title + artist."""
    kb = None
    try:
        if song.cover:
            return await message.reply_photo(song.cover, caption=text, reply_markup=kb)
    except TelegramBadRequest:
        pass  # cover URL rejected by Telegram -> text card
    try:
        return await message.reply(text, reply_markup=kb, disable_web_page_preview=True)
    except TelegramBadRequest:
        return None


async def _finish_card(card: Message | None, text: str) -> None:
    """Drop the "downloading MP3…" line once the MP3 is out."""
    if not card:
        return
    final = text.rsplit("\n", 1)[0]
    try:
        if card.photo:
            await card.edit_caption(caption=final, reply_markup=card.reply_markup)
        else:
            await card.edit_text(final, reply_markup=card.reply_markup, disable_web_page_preview=True)
    except TelegramBadRequest:
        pass


@router.message(F.chat.type == "private", MEDIA)
async def on_media(message: Message, bot: Bot, db: DB, lang: str) -> None:
    f = _file_of(message)
    async with user_lock(message.from_user.id) as ok:
        if not ok:
            await message.reply(t(lang, "busy"))
            return
        await react(message, "👀")
        status = await message.reply(t(lang, "recognizing"))
        path = None
        found = False
        try:
            path = await _fetch(bot, f.file_id, f.file_size)
            if not path:
                await message.reply(t(lang, "file_too_big"))
                return
            song = await recognizer.recognize(path)
            hint = ""
            if message.audio and not song and message.audio.title:
                hint = f"{message.audio.performer or ''} - {message.audio.title}".strip(" -")
            found = await _deliver(message, bot, db, lang, song, hint)
        except Exception:
            log.exception("recognition failed")
            await message.reply(t(lang, "error"))
        finally:
            await react(message, "🔥" if found else "🙈")
            if path:
                shutil.rmtree(path.parent, ignore_errors=True)
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


@router.callback_query(F.data.startswith("g:"))
async def cb_get_song(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    """The "🎵 Download the song" button under a downloaded video."""
    token = call.data.split(":", 1)[1]
    message = call.message
    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("🎧")
        status = await message.answer(t(lang, "recognizing"))
        tmp = None
        try:
            meta = await db.get_file(f"clip:{token}")
            hint = meta[2].get("hint", "") if meta else ""
            clip = clips_dir() / f"{token}.ogg"
            if not clip.exists():
                # clip expired: fall back to the video attached to this message
                file_id = message.video.file_id if message.video else (meta[1] if meta and meta[1] != "-" else None)
                size = message.video.file_size if message.video else None
                tmp = await _fetch(bot, file_id, size) if file_id else None
                clip = tmp
            song = await recognizer.recognize(clip) if clip else None
            await _deliver(message, bot, db, lang, song, hint)
        except Exception:
            log.exception("song button failed")
            await message.answer(t(lang, "error"))
        finally:
            if tmp:
                shutil.rmtree(tmp.parent, ignore_errors=True)
            try:
                await status.delete()
            except TelegramBadRequest:
                pass
