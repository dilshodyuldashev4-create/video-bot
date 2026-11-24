"""Inline mode: type "@bot song name" in any chat and send the track there.

Tracks the bot already has (library / cache) are sent instantly as audio. Others are
sent as a "⏳ loading" card; the MP3 is then downloaded and put into that message
(on "chosen inline result" when inline feedback is on in @BotFather, or when the
"⏳" button is pressed). Needs inline mode enabled in @BotFather (/setinline).
"""
import hashlib
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import (CallbackQuery, ChosenInlineResult, InlineKeyboardButton, InlineKeyboardMarkup,
                           InlineQuery, InlineQueryResultArticle, InlineQueryResultCachedAudio,
                           InlineQueryResultsButton, InputMediaAudio, InputTextMessageContent)

from ..common import audio_caption, bot_username, send_track
from ..config import config
from ..db import DB
from ..services import downloader
from ..texts import t
from ..utils import clean_query, esc, fmt_duration

log = logging.getLogger(__name__)
router = Router(name="inline")

MAX_RESULTS = 20
_titles: dict[str, str] = {}  # video id -> clean title, so fallbacks know what song it is
_busy: set[str] = set()       # inline messages being filled right now


def _share_kb(username: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "inline_open"), url=f"https://t.me/{username}")]])


def _rid(prefix: str, value: str) -> str:
    rid = f"{prefix}:{value}"
    return rid if len(rid) <= 64 else f"{prefix}:{hashlib.md5(value.encode()).hexdigest()}"


@router.inline_query()
async def on_inline(query: InlineQuery, db: DB, lang: str, bot: Bot) -> None:
    text = clean_query(query.query or "")
    button = InlineQueryResultsButton(text=t(lang, "inline_open" if len(text) >= 2 else "inline_hint"),
                                      start_parameter="inline")
    if len(text) < 2:
        await query.answer([], cache_time=60, button=button)
        return
    username = await bot_username(bot)
    results = []
    for item in await db.search_library(text, limit=5):
        performer, _, title = item["title"].partition(" - ")
        if not title:
            performer, title = "", item["title"]
        results.append(InlineQueryResultCachedAudio(
            id=_rid("l", item["id"][4:]), audio_file_id=item["id"][4:],
            caption=audio_caption(lang, username, title, performer), parse_mode="HTML",
            reply_markup=_share_kb(username, lang)))
    seen = {r.audio_file_id for r in results}
    for tr in await downloader.search(text, limit=15):
        if len(results) >= MAX_RESULTS:
            break
        title = downloader.clean_title(tr.title) or tr.title
        cached = await db.get_file(f"a:{tr.id}")
        if cached and cached[1] not in seen:
            meta = cached[2]
            results.append(InlineQueryResultCachedAudio(
                id=_rid("a", tr.id), audio_file_id=cached[1],
                caption=audio_caption(lang, username, meta.get("title", ""), meta.get("performer", "")),
                parse_mode="HTML", reply_markup=_share_kb(username, lang)))
            continue
        if len(_titles) > 5000:
            _titles.clear()
        _titles[tr.id] = title
        desc = " · ".join(x for x in (fmt_duration(tr.duration), tr.uploader) if x)
        results.append(InlineQueryResultArticle(
            id=_rid("y", tr.id), title=f"🎧 {title}", description=desc or None,
            thumbnail_url=f"https://i.ytimg.com/vi/{tr.id}/mqdefault.jpg",
            input_message_content=InputTextMessageContent(
                message_text=f"🎧 <b>{esc(title)}</b>\n{t(lang, 'inline_loading')}", parse_mode="HTML"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=t(lang, "inline_loading"), callback_data=f"il:{tr.id}")]]),
        ))
    await query.answer(results, cache_time=300, is_personal=False, button=button)


@router.chosen_inline_result(F.result_id.startswith("y:"))
async def on_chosen(result: ChosenInlineResult, bot: Bot, db: DB, lang: str) -> None:
    if result.inline_message_id:
        await fill_inline(bot, db, result.inline_message_id, result.result_id[2:], result.from_user.id, lang)


@router.callback_query(F.data.startswith("il:"))
async def cb_inline(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    if not call.inline_message_id:
        await call.answer()
        return
    await call.answer("⏳")
    await fill_inline(bot, db, call.inline_message_id, call.data[3:], call.from_user.id, lang)


async def _storage_chats(db: DB, user_id: int) -> list[int]:
    """Where to upload the MP3 first to get a file_id: the user's own chat with the bot,
    then the admins' (the upload is deleted right away)."""
    return list(dict.fromkeys([user_id, *config.admin_ids, *await db.admin_ids()]))


async def fill_inline(bot: Bot, db: DB, inline_message_id: str, video_id: str, user_id: int, lang: str) -> None:
    if inline_message_id in _busy:
        return
    _busy.add(inline_message_id)
    username = await bot_username(bot)
    try:
        cached = await db.get_file(f"a:{video_id}")
        if cached:
            file_id, meta = cached[1], cached[2]
        else:
            msg = None
            for chat_id in await _storage_chats(db, user_id):
                try:
                    msg = await send_track(bot, db, chat_id, video_id, lang, query=_titles.get(video_id, ""))
                    break
                except (TelegramForbiddenError, TelegramBadRequest):
                    continue  # never started the bot -> try the next chat
            if not msg or not msg.audio:
                raise downloader.DownloadFailed("no chat to upload to")
            file_id = msg.audio.file_id
            meta = {"title": msg.audio.title or "", "performer": msg.audio.performer or ""}
            try:
                await msg.delete()
            except TelegramBadRequest:
                pass
        await bot.edit_message_media(
            inline_message_id=inline_message_id,
            media=InputMediaAudio(media=file_id, caption=audio_caption(lang, username, meta.get("title", ""),
                                                                       meta.get("performer", "")),
                                  parse_mode="HTML"),
            reply_markup=_share_kb(username, lang),
        )
        await db.log_play(user_id, meta.get("title", ""), meta.get("performer", ""))
    except downloader.DownloadFailed:
        log.warning("inline download failed for %s", video_id, exc_info=True)
        await _edit_text(bot, inline_message_id, t(lang, "track_failed"))
    except Exception:
        log.exception("inline fill failed for %s", video_id)
        await _edit_text(bot, inline_message_id, t(lang, "error"))
    finally:
        _busy.discard(inline_message_id)


async def _edit_text(bot: Bot, inline_message_id: str, text: str) -> None:
    try:
        await bot.edit_message_text(text=text, inline_message_id=inline_message_id)
    except TelegramBadRequest:
        pass
