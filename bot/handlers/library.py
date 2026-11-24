"""❤️ likes and "My music", 🔥 charts, ⚡ speed up / 🌙 slowed + reverb, 📝 lyrics."""
import asyncio
import logging
import shutil
import uuid

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

from ..common import audio_caption, bot_username, react, user_lock
from ..config import config
from ..db import DB, norm_text
from ..keyboards import audio_kb, is_expanded, results_kb, results_text
from ..services import charts, lyrics, media
from ..texts import LINE, menu_labels, t
from ..utils import esc

log = logging.getLogger(__name__)
router = Router(name="library")

MY_MUSIC = "__mymusic__"
CHART_PREFIX = "__chart_"


def header_for(query: str) -> str:
    """Which header a saved list uses (search results, My music, a chart)."""
    if query == MY_MUSIC:
        return "my_music_header"
    if query.startswith(CHART_PREFIX):
        return f"chart_{query[len(CHART_PREFIX):].strip('_')}_header"
    return "results_header"


@router.callback_query(F.data == "lk")
async def cb_like(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    audio = call.message.audio if call.message else None
    if not audio:
        await call.answer()
        return
    title = " - ".join(x for x in (audio.performer, audio.title) if x) or audio.file_name or "♪"
    liked = await db.toggle_like(call.from_user.id, audio.file_unique_id, audio.file_id, title, audio.duration or 0)
    await call.answer(t(lang, "liked" if liked else "unliked"))
    try:
        await call.message.edit_reply_markup(reply_markup=audio_kb(await bot_username(bot), lang, liked=liked,
                                                                   expanded=is_expanded(call.message.reply_markup)))
    except TelegramBadRequest:
        pass


@router.message(Command("mymusic"))
@router.message(F.chat.type == "private", F.text.in_(menu_labels("menu_my_music")))
async def cmd_my_music(message: Message, db: DB, lang: str) -> None:
    likes = await db.get_likes(message.from_user.id)
    if not likes:
        await message.answer(t(lang, "my_music_empty"))
        return
    sid = await db.save_search(MY_MUSIC, likes)
    await message.answer(results_text(MY_MUSIC, likes, 0, lang, header_key="my_music_header"),
                         reply_markup=results_kb(sid, len(likes), 0))


async def send_liked(bot: Bot, chat_id: int, item: dict, lang: str, liked: bool = True) -> None:
    username = await bot_username(bot)
    performer, _, title = item["title"].partition(" - ")
    if not title:
        performer, title = "", item["title"]
    await bot.send_audio(chat_id, item["id"][4:], caption=audio_caption(lang, username, title, performer),
                         reply_markup=audio_kb(username, lang, liked=liked))


# ---------------------------------------------------------------- charts

CHART_BUTTONS = {
    **{label: "world" for label in menu_labels("menu_top_world")},
    **{label: "uz" for label in menu_labels("menu_top_uz")},
    **{label: "ru" for label in menu_labels("menu_top_ru")},
}


@router.message(Command("top"))
@router.message(F.chat.type == "private", F.text.in_(set(CHART_BUTTONS)))
async def cmd_chart(message: Message, db: DB, lang: str) -> None:
    kind = CHART_BUTTONS.get(message.text or "", "world")
    status = await message.answer("🔥")
    items = await charts.get_chart(kind)
    if not items:
        await status.edit_text(t(lang, "chart_failed"))
        return
    query = f"{CHART_PREFIX}{kind}__"
    sid = await db.save_search(query, items)
    await status.edit_text(results_text(query, items, 0, lang, header_key=header_for(query)),
                           reply_markup=results_kb(sid, len(items), 0))


# ---------------------------------------------------------------- speed up / slowed + reverb

FX_SUFFIX = {"up": "(sped up)", "slow": "(slowed + reverb)", "8d": "(8D audio)", "bass": "(bass boosted)",
             "minus": "(instrumental)"}


@router.callback_query(F.data.in_({f"fx:{m}" for m in FX_SUFFIX}))
async def cb_fx(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    audio = call.message.audio if call.message else None
    if not audio:
        await call.answer()
        return
    mode = call.data.split(":", 1)[1]
    username = await bot_username(bot)
    header = t(lang, f"fx_header_{mode}")
    suffix = FX_SUFFIX[mode]
    title = f"{audio.title or audio.file_name or 'track'} {suffix}"
    caption = audio_caption(lang, username, title, audio.performer or "", header)
    kb = audio_kb(username, lang)
    key = f"fx:{audio.file_unique_id}:{mode}"

    cached = await db.get_file(key)
    if cached:
        await call.answer()
        try:
            await bot.send_audio(call.message.chat.id, cached[1], caption=caption, reply_markup=kb)
            return
        except TelegramBadRequest:
            await db.drop_file(key)

    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("⏳")
        status = await call.message.answer("⏳")
        work = config.tmp_dir / f"fx_{uuid.uuid4().hex}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            if audio.file_size and audio.file_size > config.download_limit:
                await call.message.answer(t(lang, "file_too_big"))
                return
            src = work / "src.mp3"
            await bot.download(audio.file_id, destination=src, timeout=600)
            if mode == "minus":
                out = await media.make_minus(src, work / "out.mp3")
                if not out:
                    await call.message.answer(t(lang, "minus_mono"))
                    return
            else:
                out = await media.make_fx(src, work / "out.mp3", mode)
            if not out:
                await call.message.answer(t(lang, "error"))
                return
            thumb = await media.extract_cover(src, work / "thumb.jpg")
            sent = await bot.send_audio(
                call.message.chat.id,
                FSInputFile(out, filename=f"{audio.performer or ''} - {title}.mp3".strip(" -")[:120]),
                title=title[:64], performer=(audio.performer or "")[:64] or None,
                thumbnail=FSInputFile(thumb) if thumb else None,
                caption=caption, reply_markup=kb, request_timeout=600,
            )
            if sent.audio:
                await db.put_file(key, "audio", sent.audio.file_id, {"title": title, "performer": audio.performer})
            await db.incr("downloads")
        except Exception:
            log.exception("fx %s failed", mode)
            await call.message.answer(t(lang, "error"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


# ---------------------------------------------------------------- lyrics

def _lyric_chunks(text: str, size: int = 3800) -> list[str]:
    chunks, cur = [], ""
    for block in text.split("\n"):
        if len(cur) + len(block) + 1 > size:
            chunks.append(cur)
            cur = ""
        cur += block + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks or [text[:size]]


def audio_names(audio) -> tuple[str, str]:
    """(performer, title) of a Telegram audio, from its tags or its file name."""
    performer, title = (audio.performer or "").strip(), (audio.title or "").strip()
    if not title and audio.file_name:
        performer, _, title = audio.file_name.rsplit(".", 1)[0].partition(" - ")
        if not title:
            performer, title = "", performer
    return performer.strip(), title.strip()


async def lyrics_for(db: DB, title: str, performer: str) -> str | None:
    name = f"{performer} - {title}" if performer else title
    key = "ly:" + norm_text(name)[:200]
    cached = await db.get_file(key)
    text = cached[2].get("text") if cached else None
    if not text:
        text = await asyncio.to_thread(lyrics.find, title, performer)
        if text:
            await db.put_file(key, "lyrics", "-", {"text": text})
    return text


@router.callback_query(F.data == "ly")
async def cb_lyrics(call: CallbackQuery, db: DB, lang: str) -> None:
    """📝 under an MP3: the song's lyrics."""
    audio = call.message.audio if call.message else None
    if not audio:
        await call.answer("😔", show_alert=False)
        return
    performer, title = audio_names(audio)
    name = f"{performer} - {title}" if performer else title
    await call.answer("📝")
    text = await lyrics_for(db, title, performer)
    if not text:
        await call.message.reply(t(lang, "lyrics_none", name=esc(name)))
        return
    chunks = _lyric_chunks(esc(text))
    head = t(lang, "lyrics_title", name=esc(name)) + "\n" + LINE + "\n"
    for i, chunk in enumerate(chunks):
        await call.message.reply((head if i == 0 else "") + chunk)
