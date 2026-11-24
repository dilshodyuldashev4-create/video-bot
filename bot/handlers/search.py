"""Text -> list of 10 songs with number buttons -> MP3."""
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from ..common import react, send_song, send_track, split_query, user_lock
from ..db import DB
from .library import header_for, send_liked
from ..keyboards import PAGE_SIZE, results_kb, results_text
from ..services import downloader
from ..texts import t
from ..utils import clean_query, esc

log = logging.getLogger(__name__)
router = Router(name="search")


@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def on_text(message: Message, db: DB, lang: str) -> None:
    query = clean_query(message.text)
    if len(query) < 2:
        return
    await react(message, "👀")
    status = await message.answer(t(lang, "searching"))
    lib = await db.search_library(query, limit=5)  # songs people sent to the bot come first
    tracks = await downloader.search(query, limit=30 - len(lib))
    if not tracks and not lib:
        await status.edit_text(t(lang, "nothing_found", q=esc(query)))
        await react(message, "🙈")
        return
    await react(message, "🔥")
    results = lib + [tr.as_dict() for tr in tracks]
    sid = await db.save_search(query, results)
    await status.edit_text(results_text(query, results, 0, lang), reply_markup=results_kb(sid, len(results), 0))


@router.callback_query(F.data.startswith("p:"))
async def cb_page(call: CallbackQuery, db: DB, lang: str) -> None:
    _, sid, page = call.data.split(":")
    found = await db.get_search(int(sid))
    if not found:
        await call.answer(t(lang, "search_expired"), show_alert=True)
        return
    query, results = found
    page = max(0, min(int(page), (len(results) - 1) // PAGE_SIZE))
    header = header_for(query)
    try:
        await call.message.edit_text(results_text(query, results, page, lang, header_key=header),
                                     reply_markup=results_kb(int(sid), len(results), page))
    except TelegramBadRequest:  # "message is not modified" when there is a single page
        pass
    await call.answer()


@router.callback_query(F.data.startswith("t:"))
async def cb_track(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    _, sid, idx = call.data.split(":")
    found = await db.get_search(int(sid))
    if not found or int(idx) >= len(found[1]):
        await call.answer(t(lang, "search_expired"), show_alert=True)
        return
    track = found[1][int(idx)]
    if track["id"].startswith("fid:"):  # from "My music": already on Telegram, instant
        await call.answer()
        await send_liked(bot, call.message.chat.id, track, lang, liked=not track.get("lib"))
        return
    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("⏳")
        status = await call.message.answer(t(lang, "downloading"))
        try:
            if track["id"].startswith("q:"):  # chart entry: "Artist - Title", find it first
                await send_by_query(bot, db, call.message.chat.id, track["id"][2:], lang)
            else:
                await send_track(bot, db, call.message.chat.id, track["id"], lang,
                                 query=downloader.clean_title(track["title"]))
        except downloader.DownloadFailed:
            log.warning("audio download failed for %s", track["id"], exc_info=True)
            await call.message.answer(t(lang, "track_failed"))
        except Exception:
            log.exception("send_track failed")
            await call.message.answer(t(lang, "error"))
        finally:
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


async def send_by_query(bot: Bot, db: DB, chat_id: int, query: str, lang: str) -> None:
    title, artist = split_query(query)
    await send_song(bot, db, chat_id, title, artist, lang)
