"""🎵 similar tracks, 🔔 artist follows + new-release alerts, 📂 playlists, 🎬 Stories clips, 🎛 effects menu."""
import asyncio
import logging
import shutil
import time
import uuid

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message)

from ..common import bot_username, react, user_lock
from ..config import config
from ..db import DB, norm_text
from ..keyboards import (audio_kb, is_expanded, is_liked_kb, playlist_actions_kb, playlist_pick_kb, playlists_kb,
                         results_kb, results_text)
from ..services import deezer, downloader, media, story
from ..texts import TEXTS, menu_labels, t
from ..utils import esc
from .library import audio_names, lyrics_for

log = logging.getLogger(__name__)
router = Router(name="music")

SIM_PREFIX = "__sim__"
PL_PREFIX = "__pl__"
RELEASE_CHECK_EVERY = 6 * 3600


def _audio_title(audio) -> str:
    performer, title = audio_names(audio)
    return f"{performer} - {title}" if performer else (title or "♪")


# ---------------------------------------------------------------- 🎛 effects menu open / close

@router.callback_query(F.data.in_({"fxm", "fxb"}))
async def cb_fx_menu(call: CallbackQuery, bot: Bot, lang: str) -> None:
    if not call.message or not call.message.audio:
        await call.answer()
        return
    liked = is_liked_kb(call.message.reply_markup)
    try:
        await call.message.edit_reply_markup(
            reply_markup=audio_kb(await bot_username(bot), lang, liked=liked, expanded=call.data == "fxm"))
    except TelegramBadRequest:
        pass
    await call.answer()


# ---------------------------------------------------------------- 🎵 similar tracks

async def similar_items(db: DB, title: str, performer: str) -> list[dict]:
    key = "sim:" + norm_text(f"{performer} {title}")[:200]
    cached = await db.get_file(key)
    if cached and cached[2].get("items"):
        return cached[2]["items"]
    names: list[str] = []
    try:
        names = await asyncio.to_thread(deezer.similar, title, performer)
    except Exception as e:  # noqa: BLE001
        log.info("deezer similar failed: %s", str(e)[:120])
    items = [{"id": f"q:{n}"[:200], "title": n, "duration": 0} for n in names]
    if not items and performer:  # fallback: more songs of the same artist
        tracks = await downloader.search(f"{performer} songs", limit=20)
        items = [{"id": tr.id, "title": downloader.clean_title(tr.title) or tr.title, "duration": tr.duration}
                 for tr in tracks if norm_text(title) not in norm_text(tr.title)]
    if items:
        await db.put_file(key, "similar", "-", {"items": items})
    return items


@router.callback_query(F.data == "sim")
async def cb_similar(call: CallbackQuery, db: DB, lang: str) -> None:
    audio = call.message.audio if call.message else None
    if not audio:
        await call.answer()
        return
    await call.answer("🎵")
    performer, title = audio_names(audio)
    status = await call.message.answer(t(lang, "searching"))
    items = await similar_items(db, title, performer)
    if not items:
        await status.edit_text(t(lang, "similar_none"))
        return
    query = SIM_PREFIX + _audio_title(audio)
    sid = await db.save_search(query, items)
    await status.edit_text(results_text(query, items, 0, lang, header_key="similar_header"),
                           reply_markup=results_kb(sid, len(items), 0))


# ---------------------------------------------------------------- 🔔 follow an artist

@router.callback_query(F.data == "fol")
async def cb_follow(call: CallbackQuery, db: DB, lang: str) -> None:
    audio = call.message.audio if call.message else None
    performer = audio_names(audio)[0] if audio else ""
    if not performer:
        await call.answer(t(lang, "follow_none"), show_alert=True)
        return
    main = performer.split(",")[0].split(" feat")[0].split(" ft.")[0].split(" & ")[0].strip()
    try:
        artist = await asyncio.to_thread(deezer.find_artist, main)
    except Exception as e:  # noqa: BLE001
        log.info("deezer artist failed: %s", str(e)[:120])
        artist = None
    if not artist:
        await call.answer(t(lang, "follow_none"), show_alert=True)
        return
    on = await db.toggle_follow(call.from_user.id, artist["id"], artist["name"])
    await call.answer(t(lang, "follow_on" if on else "follow_off", name=artist["name"]), show_alert=True)
    if on:
        state, _ = await db.artist_state(artist["id"])
        if state is None:  # remember the current newest release so only newer ones are announced
            try:
                rel = await asyncio.to_thread(deezer.latest_release, artist["id"])
                if rel:
                    await db.set_artist_state(artist["id"], rel["id"], rel["title"])
            except Exception:  # noqa: BLE001
                pass


def _follows_kb(rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔕 {name}", callback_data=f"unf:{aid}")] for aid, name in rows[:40]])


@router.message(Command("follows"))
async def cmd_follows(message: Message, db: DB, lang: str) -> None:
    rows = await db.follows_of(message.from_user.id)
    if not rows:
        await message.answer(t(lang, "follows_empty"))
        return
    await message.answer(t(lang, "follows_header"), reply_markup=_follows_kb(rows))


@router.callback_query(F.data.startswith("unf:"))
async def cb_unfollow(call: CallbackQuery, db: DB, lang: str) -> None:
    aid = call.data.split(":", 1)[1]
    name = dict(await db.follows_of(call.from_user.id)).get(aid)
    if name:
        await db.toggle_follow(call.from_user.id, aid, name)
        await call.answer(t(lang, "follow_off", name=name))
    else:
        await call.answer()
    rows = await db.follows_of(call.from_user.id)
    try:
        if rows:
            await call.message.edit_reply_markup(reply_markup=_follows_kb(rows))
        else:
            await call.message.edit_text(t(lang, "follows_empty"))
    except TelegramBadRequest:
        pass


async def check_releases(bot: Bot, db: DB) -> int:
    """Announce new releases of followed artists. Returns how many alerts were sent."""
    sent = 0
    for aid, name in await db.followed_artists():
        try:
            rel = await asyncio.to_thread(deezer.latest_release, aid)
        except Exception as e:  # noqa: BLE001
            log.info("release check %s failed: %s", name, str(e)[:120])
            continue
        if not rel:
            continue
        known, _ = await db.artist_state(aid)
        await db.set_artist_state(aid, rel["id"], rel["title"])
        if known is None or known == rel["id"] or not deezer.is_fresh(rel["date"]):
            continue
        for uid in await db.followers(aid):
            lang = await db.get_lang(uid) or "ru"
            caption = t(lang, "new_release", artist=esc(name), title=esc(rel["title"]))
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=t(lang, "btn_listen"), callback_data=f"nr:{aid}")]])
            try:
                if rel["cover"]:
                    await bot.send_photo(uid, rel["cover"], caption=caption, reply_markup=kb)
                else:
                    await bot.send_message(uid, caption, reply_markup=kb)
                sent += 1
            except (TelegramForbiddenError, TelegramBadRequest):
                pass
            await asyncio.sleep(0.05)
        await asyncio.sleep(1)
    return sent


async def release_watcher(bot: Bot, db: DB) -> None:
    await asyncio.sleep(120)
    while True:
        try:
            n = await check_releases(bot, db)
            log.info("new-release check done, %d alerts", n)
        except Exception:
            log.exception("release watcher failed")
        await asyncio.sleep(RELEASE_CHECK_EVERY)


@router.callback_query(F.data.startswith("nr:"))
async def cb_new_release(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    from .search import send_by_query  # search imports library; avoid an import cycle at load time

    aid = call.data.split(":", 1)[1]
    _, title = await db.artist_state(aid)
    name = dict(await db.followed_artists()).get(aid, "")
    if not title:
        await call.answer(t(lang, "link_expired"), show_alert=True)
        return
    async with user_lock(call.from_user.id) as ok:
        if not ok:
            await call.answer(t(lang, "busy"))
            return
        await call.answer("⏳")
        status = await call.message.answer(t(lang, "downloading"))
        try:
            await send_by_query(bot, db, call.message.chat.id, f"{name} - {title}" if name else title, lang)
        except downloader.DownloadFailed:
            await call.message.answer(t(lang, "track_failed"))
        except Exception:
            log.exception("new release send failed")
            await call.message.answer(t(lang, "error"))
        finally:
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


# ---------------------------------------------------------------- 📂 playlists

_pending: dict[int, tuple[float, dict]] = {}  # user -> (time, track) waiting for a new playlist name
PENDING_TTL = 600


def _track_of(audio) -> dict:
    return {"unique_id": audio.file_unique_id, "file_id": audio.file_id, "title": _audio_title(audio),
            "duration": audio.duration or 0}


@router.callback_query(F.data == "pl")
async def cb_playlist_pick(call: CallbackQuery, db: DB, lang: str) -> None:
    if not call.message or not call.message.audio:
        await call.answer()
        return
    playlists = await db.playlists_of(call.from_user.id)
    await call.answer(t(lang, "pl_choose"))
    try:
        await call.message.edit_reply_markup(reply_markup=playlist_pick_kb(playlists, lang))
    except TelegramBadRequest:
        pass


async def _restore_kb(call: CallbackQuery, bot: Bot, lang: str) -> None:
    try:
        await call.message.edit_reply_markup(reply_markup=audio_kb(await bot_username(bot), lang))
    except TelegramBadRequest:
        pass


@router.callback_query(F.data.startswith("pla:"))
async def cb_playlist_add(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    audio = call.message.audio if call.message else None
    pl = await db.get_playlist(pid=int(call.data.split(":", 1)[1]))
    if not audio or not pl or pl["owner"] != call.from_user.id:
        await call.answer(t(lang, "link_expired"), show_alert=True)
        return
    tr = _track_of(audio)
    added = await db.add_to_playlist(pl["id"], tr["unique_id"], tr["file_id"], tr["title"], tr["duration"])
    await call.answer(t(lang, "pl_added" if added else "pl_exists", name=pl["name"]))
    await _restore_kb(call, bot, lang)


@router.callback_query(F.data == "pln")
async def cb_playlist_new(call: CallbackQuery, bot: Bot, lang: str) -> None:
    audio = call.message.audio if call.message else None
    if not audio:
        await call.answer()
        return
    _pending[call.from_user.id] = (time.time(), _track_of(audio))
    await call.answer()
    await _restore_kb(call, bot, lang)
    await call.message.answer(t(lang, "pl_ask_name"))


def _all_menu_labels() -> set[str]:
    return {v for table in TEXTS.values() for k, v in table.items() if k.startswith("menu_") and "{" not in v}


def _waiting_for_name(message: Message) -> bool:
    if not message.from_user or message.from_user.id not in _pending:
        return False
    at, _ = _pending[message.from_user.id]
    text = message.text or ""
    if time.time() - at > PENDING_TTL or text.startswith(("/", "📊", "http")) or text in _all_menu_labels():
        _pending.pop(message.from_user.id, None)
        return False
    return True


@router.message(F.chat.type == "private", F.text, _waiting_for_name)
async def on_playlist_name(message: Message, db: DB, lang: str) -> None:
    _, tr = _pending.pop(message.from_user.id)
    name = " ".join(message.text.split())[:60]
    pl = await db.create_playlist(message.from_user.id, name)
    await db.add_to_playlist(pl["id"], tr["unique_id"], tr["file_id"], tr["title"], tr["duration"])
    await react(message, "🔥")
    await show_playlist(message, db, lang, pl, mine=True)


async def show_playlist(message: Message, db: DB, lang: str, pl: dict, mine: bool) -> None:
    items = await db.playlist_items(pl["id"])
    query = PL_PREFIX + pl["name"]
    username = await bot_username(message.bot)
    if not items:
        await message.answer(t(lang, "playlist_empty"),
                             reply_markup=playlist_actions_kb(0, 0, pl, username, lang, mine))
        return
    sid = await db.save_search(query, items)
    await message.answer(results_text(query, items, 0, lang, header_key="playlist_header"),
                         reply_markup=playlist_actions_kb(sid, len(items), pl, username, lang, mine))


@router.message(Command("playlists"))
@router.message(F.chat.type == "private", F.text.in_(menu_labels("menu_playlists")))
async def cmd_playlists(message: Message, db: DB, lang: str) -> None:
    playlists = await db.playlists_of(message.from_user.id)
    if not playlists:
        await message.answer(t(lang, "playlists_empty"))
        return
    await message.answer(t(lang, "playlists_header"), reply_markup=playlists_kb(playlists))


@router.callback_query(F.data.startswith("plo:"))
async def cb_playlist_open(call: CallbackQuery, db: DB, lang: str) -> None:
    pl = await db.get_playlist(pid=int(call.data.split(":", 1)[1]))
    await call.answer()
    if pl:
        await show_playlist(call.message, db, lang, pl, mine=pl["owner"] == call.from_user.id)


@router.callback_query(F.data.startswith("pld:"))
async def cb_playlist_delete(call: CallbackQuery, db: DB, lang: str) -> None:
    if await db.delete_playlist(int(call.data.split(":", 1)[1]), call.from_user.id):
        await call.answer(t(lang, "pl_deleted"))
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass
    else:
        await call.answer()


@router.callback_query(F.data.startswith("plc:"))
async def cb_playlist_copy(call: CallbackQuery, db: DB, lang: str) -> None:
    src = await db.get_playlist(code=call.data.split(":", 1)[1])
    if not src:
        await call.answer(t(lang, "link_expired"), show_alert=True)
        return
    new = await db.create_playlist(call.from_user.id, src["name"])
    for it in await db.playlist_items(src["id"]):
        fid = it["id"][4:]
        await db.add_to_playlist(new["id"], fid[-40:], fid, it["title"], it["duration"])
    await call.answer(t(lang, "pl_saved", name=src["name"]), show_alert=True)


@router.message(CommandStart(deep_link=True), F.chat.type == "private")
async def start_playlist_link(message: Message, command: CommandObject, db: DB, lang: str) -> None:
    """t.me/<bot>?start=pl_<code> opens a shared playlist (other deep links fall through to /start)."""
    from .start import cmd_start

    arg = command.args or ""
    pl = await db.get_playlist(code=arg[3:]) if arg.startswith("pl_") else None
    if not pl:
        await cmd_start(message, lang)
        return
    await show_playlist(message, db, lang, pl, mine=pl["owner"] == message.from_user.id)


# ---------------------------------------------------------------- 🎬 clip for Stories

@router.callback_query(F.data == "st")
async def cb_story(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
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
        await call.answer("🎬")
        status = await call.message.answer("⏳🎬")
        work = config.tmp_dir / f"st_{uuid.uuid4().hex}"
        work.mkdir(parents=True, exist_ok=True)
        try:
            src = work / "src.mp3"
            await bot.download(audio.file_id, destination=src, timeout=600)
            cover = await media.extract_cover(src, work / "cover.jpg")
            if not cover and audio.thumbnail:
                cover = work / "thumb.jpg"
                await bot.download(audio.thumbnail.file_id, destination=cover)
            performer, title = audio_names(audio)
            line = story.lyric_line(await lyrics_for(db, title, performer)) if title else ""
            frame = await asyncio.to_thread(story.render_frame, cover, title or "♪", performer, line,
                                            await bot_username(bot), work / "frame.png")
            out = await story.make_clip(src, frame, work / "story.mp4")
            if not out:
                await call.message.answer(t(lang, "error"))
                return
            await bot.send_video(call.message.chat.id, FSInputFile(out, filename="story.mp4"), width=1080,
                                 height=1920, duration=story.CLIP_SECONDS, supports_streaming=True,
                                 caption=t(lang, "story_caption"), request_timeout=300)
        except Exception:
            log.exception("story clip failed")
            await call.message.answer(t(lang, "error"))
        finally:
            shutil.rmtree(work, ignore_errors=True)
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


# ---------------------------------------------------------------- 🎧 Mini App

@router.message(Command("app"))
async def cmd_app(message: Message, lang: str) -> None:
    from aiogram.types import WebAppInfo

    from ..webapp.server import public_url

    url = public_url()
    if not url or message.chat.type != "private":
        await message.answer(t(lang, "app_off"))
        return
    await message.answer(t(lang, "app_text"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_app"), web_app=WebAppInfo(url=url))]]))
