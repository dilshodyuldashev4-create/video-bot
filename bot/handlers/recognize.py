"""Shazam: video / audio / voice / video note -> song name -> MP3."""
import logging
import re
import shutil
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from ..common import react, send_song, user_lock
from ..config import config
from ..db import DB
from ..keyboards import video_more_kb
from ..services import downloader, recognizer
from ..services.recognizer import Song
from ..texts import t
from ..utils import canonical_key, esc
from .links import clips_dir, link_of

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


def audio_tags(message: Message) -> tuple[str, str]:
    """(performer, title) of a sent music file from its tags or 'Artist - Title.mp3' file name."""
    a = message.audio
    performer, title = (a.performer or "").strip(), (a.title or "").strip()
    if not title:
        stem = re.sub(r"\.(mp3|m4a|ogg|opus|flac|wav|aac)$", "", a.file_name or "", flags=re.I)
        stem = re.sub(r"[_]+", " ", stem).strip()
        artist, sep, name = stem.partition(" - ")
        if sep and name.strip():
            performer, title = performer or artist.strip(), name.strip()
        elif stem and performer:
            title = stem
    return performer, title


async def save_to_library(message: Message, db: DB) -> str | None:
    """Store a sent song (with a real artist and title) in the library. Returns 'Artist - Title'."""
    if not message.audio:
        return None
    performer, title = audio_tags(message)
    if not (performer and title) or re.fullmatch(r"(audio|track|unknown|без названия)\s*\d*", title, re.I):
        return None
    await db.add_to_library(message.audio.file_unique_id, message.audio.file_id, title, performer,
                            message.audio.duration or 0, message.from_user.id if message.from_user else None)
    return f"{performer} - {title}"


@router.message(F.chat.type == "private", MEDIA)
async def on_media(message: Message, bot: Bot, db: DB, lang: str) -> None:
    f = _file_of(message)
    if name := await save_to_library(message, db):
        # a tagged MP3: it goes straight into the bot's library, no need to Shazam it
        await react(message, "🔥")
        await message.reply(t(lang, "lib_added", name=esc(name)))
        return
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
            if song and message.audio:  # an untagged MP3: keep it in the library under its real name
                await db.add_to_library(message.audio.file_unique_id, message.audio.file_id, song.title,
                                        song.artist, message.audio.duration or 0, message.from_user.id)
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
    await offer_video_tools(message, db, lang)


async def offer_video_tools(message: Message, db: DB, lang: str) -> None:
    """Under a video the user sent: ⭕ make a video note / 🎙 a voice message from it."""
    video = message.video or (message.document if message.document and
                              (message.document.mime_type or "").startswith("video/") else None)
    if not video:
        return
    token = uuid.uuid4().hex[:12]
    await db.put_file(f"uv:{token}", "video", video.file_id, {"size": video.file_size or 0})
    try:
        await message.reply(t(lang, "video_more"), reply_markup=video_more_kb(token, lang))
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


@router.callback_query(F.data.startswith("dl:s:"))
async def cb_link_shazam(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    """🔍 under a pasted link: download the audio, recognise it, send the song as MP3."""
    token = call.data.split(":", 2)[2]
    link = await link_of(db, token)
    if not link:
        await call.answer(t(lang, "link_expired"), show_alert=True)
        return
    url, platform = link
    message = call.message
    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("🔍")
        status = await message.answer(t(lang, "recognizing"))
        audio = None
        try:
            key = canonical_key(url, platform)
            vid = key.split(":", 1)[1] if key.startswith("youtube:") else key
            audio = await downloader.download_audio(vid, url=None if key.startswith("youtube:") else url)
            song = await recognizer.recognize(audio.path)
            await _deliver(message, bot, db, lang, song)
        except downloader.DownloadFailed:
            log.warning("shazam link download failed: %s", url, exc_info=True)
            await message.answer(t(lang, "dl_failed"))
        except Exception:
            log.exception("shazam link failed: %s", url)
            await message.answer(t(lang, "error"))
        finally:
            if audio:
                shutil.rmtree(audio.path.parent, ignore_errors=True)
            try:
                await status.delete()
            except TelegramBadRequest:
                pass
