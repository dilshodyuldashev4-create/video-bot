"""🔔 ringtones, ⭕ video -> video note / 🎙 voice, 🎧 music by mood, 📊 «Твой год» card."""
import asyncio
import datetime
import logging
import re
import shutil
import uuid

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, InlineKeyboardMarkup, Message

from ..common import bot_username, user_lock
from ..config import config
from ..db import DB
from ..keyboards import MOODS, mood_kb, results_kb, results_text, share_row
from ..services import downloader, media, wrapped
from ..texts import menu_labels, t
from ..utils import esc

log = logging.getLogger(__name__)
router = Router(name="tools")


async def _drop(msg: Message | None) -> None:
    if msg:
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass


# ---------------------------------------------------------------- ringtone

def _safe(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "", name).strip()[:60] or "ringtone"


@router.callback_query(F.data == "rt")
async def cb_ringtone(call: CallbackQuery, bot: Bot, lang: str) -> None:
    audio = call.message.audio if call.message else None
    if not audio:
        await call.answer()
        return
    if audio.file_size and audio.file_size > config.download_limit:
        await call.answer(t(lang, "file_too_big"), show_alert=True)
        return
    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("🔔")
        status = await call.message.answer("⏳🔔")
        work = config.tmp_dir / f"rt_{uuid.uuid4().hex}"
        work.mkdir(parents=True, exist_ok=True)
        name = " - ".join(x for x in (audio.performer, audio.title) if x) or (audio.file_name or "ringtone").rsplit(".", 1)[0]
        try:
            src = work / "src.mp3"
            await bot.download(audio.file_id, destination=src, timeout=600)
            m4r, mp3 = await media.make_ringtone(src, work, _safe(name))
            if not m4r and not mp3:
                await call.message.answer(t(lang, "error"))
                return
            caption = t(lang, "ringtone_caption", name=esc(name))
            files = [p for p in (m4r, mp3) if p]
            for i, path in enumerate(files):
                await bot.send_document(call.message.chat.id, FSInputFile(path, filename=path.name),
                                        caption=caption if i == len(files) - 1 else None, request_timeout=300)
        except Exception:
            log.exception("ringtone failed")
            await call.message.answer(t(lang, "error"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
            await _drop(status)


# ---------------------------------------------------------------- video -> video note / voice

@router.callback_query(F.data.regexp(r"^vn:(note|voice)(:|$)"))
async def cb_video_note(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    parts = call.data.split(":")
    mode = parts[1]
    file_id, size = None, None
    if len(parts) > 2:
        found = await db.get_file(f"uv:{parts[2]}")
        if found:
            file_id = found[1]
            size = found[2].get("size")
    elif call.message and call.message.video:
        file_id, size = call.message.video.file_id, call.message.video.file_size
    if not file_id:
        await call.answer(t(lang, "link_expired"), show_alert=True)
        return
    if size and size > config.download_limit:
        await call.answer(t(lang, "file_too_big"), show_alert=True)
        return
    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("⏳")
        status = await call.message.answer("⏳")
        work = config.tmp_dir / f"vn_{uuid.uuid4().hex}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            src = work / "src.mp4"
            await bot.download(file_id, destination=src, timeout=600)
            chat = call.message.chat.id
            if mode == "note":
                out = await media.to_video_note(src, work / "note.mp4")
                if out:
                    await bot.send_video_note(chat, FSInputFile(out), length=512, request_timeout=300)
            else:
                out = await media.to_voice(src, work / "voice.ogg")
                if out:
                    await bot.send_voice(chat, FSInputFile(out), request_timeout=300)
            if not out:
                await call.message.answer(t(lang, "error"))
        except Exception:
            log.exception("video %s failed", mode)
            await call.message.answer(t(lang, "error"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
            await _drop(status)


# ---------------------------------------------------------------- music by mood

MOOD_QUERIES = {
    "sad": ("uzbek sad songs", "грустные песни хиты"),
    "car": ("uzbek music for car bass", "музыка в машину"),
    "gym": ("workout music gym phonk", "uzbek remix gym"),
    "toy": ("uzbek to'y qo'shiqlari", "o'zbek to'y raqs qo'shiqlari"),
    "chill": ("uzbek chill songs", "lofi chill hits"),
    "love": ("uzbek sevgi qo'shiqlari", "песни о любви хиты"),
}
assert set(MOOD_QUERIES) == set(MOODS)


@router.message(Command("mood"))
@router.message(F.chat.type == "private", F.text.in_(menu_labels("menu_mood")))
async def cmd_mood(message: Message, lang: str) -> None:
    await message.answer(t(lang, "mood_pick"), reply_markup=mood_kb(lang))


async def mood_tracks(mood: str) -> list[dict]:
    year = datetime.date.today().year
    lists = await asyncio.gather(*(downloader.search(f"{q} {year}", limit=15) for q in MOOD_QUERIES[mood]))
    seen, out = set(), []
    for i in range(max(map(len, lists), default=0)):  # interleave the two searches
        for lst in lists:
            if i < len(lst) and lst[i].id not in seen:
                seen.add(lst[i].id)
                out.append(lst[i].as_dict())
    return out[:30]


@router.callback_query(F.data.startswith("mood:"))
async def cb_mood(call: CallbackQuery, db: DB, lang: str) -> None:
    mood = call.data.split(":", 1)[1]
    if mood not in MOOD_QUERIES:
        await call.answer()
        return
    await call.answer("🎧")
    status = await call.message.answer(t(lang, "searching"))
    items = await mood_tracks(mood)
    if not items:
        await status.edit_text(t(lang, "chart_failed"))
        return
    query = t(lang, f"mood_{mood}")
    sid = await db.save_search(query, items)
    await status.edit_text(results_text(query, items, 0, lang), reply_markup=results_kb(sid, len(items), 0))


# ---------------------------------------------------------------- «Твой год»

@router.message(Command("wrapped"))
@router.message(F.chat.type == "private", F.text.regexp(r"^📊 "))
async def cmd_wrapped(message: Message, bot: Bot, db: DB, lang: str) -> None:
    year = datetime.date.today().year
    stats = await db.year_stats(message.from_user.id, year)
    if stats["total"] < 3:
        await message.answer(t(lang, "wrapped_empty"))
        return
    username = await bot_username(bot)
    labels = {k: t(lang, f"wr_{k}", year=year) for k in ("title", "tracks", "artists", "songs", "days")}
    work = config.tmp_dir / f"wr_{uuid.uuid4().hex}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        path = await asyncio.to_thread(wrapped.render, stats, labels, username, work / "wrapped.png")
        await message.answer_photo(BufferedInputFile(path.read_bytes(), filename=f"wrapped_{year}.png"),
                                   caption=t(lang, "wrapped_caption", year=year, bot=username),
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[share_row(username, lang)]))
    except Exception:
        log.exception("wrapped failed")
        await message.answer(t(lang, "error"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
