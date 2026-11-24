"""YouTube / Instagram / TikTok link -> choice: 🎬 video in good quality, 🎵 audio MP3,
🔍 find the music (Shazam; handled in recognize.py)."""
import logging
import shutil
import uuid

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.media_group import MediaGroupBuilder

from ..common import _send_cached as send_cached_audio, _send_fresh, bot_username, react, send_track, user_lock
from ..config import config
from ..db import DB
from ..keyboards import link_kb, video_kb
from ..services import downloader, media
from ..texts import PLATFORM_ICONS, t
from ..utils import URL_RE, canonical_key, detect_platform, extract_url

log = logging.getLogger(__name__)
router = Router(name="links")

PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")


def clips_dir():
    d = config.data_dir / "clips"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _send_cached(message: Message, cached: tuple, lang: str, username: str, platform: str) -> bool:
    kind, file_id, meta = cached
    token = meta.get("token") or ""
    caption = video_caption(lang, username, meta.get("platform") or platform)
    kb = video_kb(token, username, lang)
    try:
        if kind == "video":
            await message.answer_video(file_id, caption=caption, reply_markup=kb, supports_streaming=True)
        elif kind == "photo":
            await message.answer_photo(file_id, caption=caption, reply_markup=kb)
        else:  # album
            group = MediaGroupBuilder()
            for item in meta["items"]:
                group.add(type=item["t"], media=item["id"])
            await message.answer_media_group(group.build())
            await message.answer(caption, reply_markup=kb)
        return True
    except TelegramBadRequest:
        return False


def video_caption(lang: str, username: str, platform: str) -> str:
    icon, name = PLATFORM_ICONS.get(platform, ("📥", platform.capitalize() or "Web"))
    return t(lang, "video_caption", icon=icon, platform=name, bot=username)


@router.message(F.text.regexp(URL_RE, mode="search") | F.caption.regexp(URL_RE, mode="search"))
async def on_link(message: Message, bot: Bot, db: DB, lang: str) -> None:
    """A link: ask what to download (video / audio / find the music)."""
    url = extract_url(message.text or message.caption)
    platform = detect_platform(url) if url else None
    if not platform:
        if message.chat.type == "private":
            await message.reply(t(lang, "unsupported_link"))
        return
    if message.chat.type != "private":
        # groups: no menu, the video is downloaded straight away for everyone in the chat
        await react(message, "👀")
        done = await run_link(message, bot, db, lang, message.from_user.id if message.from_user else message.chat.id,
                              url, platform, "v", quiet_busy=True)
        await react(message, "🔥" if done else "😢")
        return
    token = uuid.uuid4().hex[:16]
    await db.put_file(f"lnk:{token}", "link", url, {"platform": platform})
    icon, name = PLATFORM_ICONS.get(platform, ("📥", platform.capitalize()))
    await message.reply(t(lang, "link_choice", icon=icon, platform=name), reply_markup=link_kb(token, lang),
                        disable_web_page_preview=True)


async def link_of(db: DB, token: str) -> tuple[str, str] | None:
    row = await db.get_file(f"lnk:{token}")
    return (row[1], row[2].get("platform") or detect_platform(row[1]) or "") if row else None


@router.callback_query(F.data.startswith("dl:v:") | F.data.startswith("dl:a:"))
async def cb_link(call: CallbackQuery, bot: Bot, db: DB, lang: str) -> None:
    _, mode, token = call.data.split(":", 2)
    link = await link_of(db, token)
    if not link:
        await call.answer(t(lang, "link_expired"), show_alert=True)
        return
    url, platform = link
    await call.answer("🎬" if mode == "v" else "🎵")
    await run_link(call.message, bot, db, lang, call.from_user.id, url, platform, mode)


async def run_link(message: Message, bot: Bot, db: DB, lang: str, user_id: int, url: str, platform: str,
                   mode: str, quiet_busy: bool = False) -> bool:
    """Download a link as video ("v") or audio ("a") into message's chat. True on success."""
    async with user_lock(user_id) as ok:
        if not ok:
            if not quiet_busy:
                await message.answer(t(lang, "busy"))
            return False
        username = await bot_username(bot)
        status = await message.answer(t(lang, "downloading"))
        try:
            if mode == "v":
                await _handle(message, bot, db, lang, username, url, platform)
            else:
                await send_link_audio(bot, db, message.chat.id, lang, url, platform)
            return True
        except downloader.TooBig:
            await message.answer(t(lang, "too_big"))
        except downloader.DownloadFailed:
            log.warning("download failed (%s): %s", mode, url, exc_info=True)
            await message.answer(t(lang, "dl_failed"))
        except Exception:
            log.exception("link handler failed: %s", url)
            await message.answer(t(lang, "error"))
        finally:
            try:
                await status.delete()
            except TelegramBadRequest:
                pass
        return False


async def send_link_audio(bot: Bot, db: DB, chat_id: int, lang: str, url: str, platform: str) -> Message:
    """🎵 Audio of the linked video as MP3 (cached by link)."""
    key = canonical_key(url, platform)
    if key.startswith("youtube:"):
        return await send_track(bot, db, chat_id, key.split(":", 1)[1], lang)
    username = await bot_username(bot)
    akey = "la:" + key
    if msg := await send_cached_audio(bot, db, akey, chat_id, lang, username, None, None):
        return msg
    audio = await downloader.download_audio(key, url=url)
    return await _send_fresh(bot, db, akey, chat_id, lang, username, audio, None, None)


async def _handle(message: Message, bot: Bot, db: DB, lang: str, username: str, url: str, platform: str) -> None:
    key = "v:" + canonical_key(url, platform)
    cached = await db.get_file(key)
    if cached and await _send_cached(message, cached, lang, username, platform):
        await db.incr("downloads")
        return

    res = await downloader.download_video(url, platform)
    try:
        token = uuid.uuid4().hex[:16]
        caption = video_caption(lang, username, platform)
        kb = video_kb(token, username, lang)
        videos = [p for p in res.files if p.suffix.lower() not in PHOTO_EXT]

        # keep a small audio copy so "Download the song" works instantly later
        if videos:
            await media.extract_audio(videos[0], clips_dir() / f"{token}.ogg")

        if len(res.files) == 1:
            path = res.files[0]
            if path.suffix.lower() in PHOTO_EXT:
                sent = await message.answer_photo(FSInputFile(path), caption=caption, reply_markup=kb)
                kind, file_id, items = "photo", sent.photo[-1].file_id, []
            else:
                sent = await _send_video(message, path, caption, kb)
                kind, file_id, items = "video", sent.video.file_id if sent.video else "", []
        else:
            group = MediaGroupBuilder()
            for path in res.files[:10]:
                if path.suffix.lower() in PHOTO_EXT:
                    group.add_photo(media=FSInputFile(path))
                else:
                    info = await media.probe(path)
                    group.add_video(media=FSInputFile(path), width=info["width"] or None,
                                    height=info["height"] or None, duration=int(info["duration"]) or None,
                                    supports_streaming=True)
            sent_msgs = await message.answer_media_group(group.build(), request_timeout=900)
            await message.answer(caption, reply_markup=kb)
            items = []
            for m in sent_msgs:
                if m.video:
                    items.append({"t": "video", "id": m.video.file_id})
                elif m.photo:
                    items.append({"t": "photo", "id": m.photo[-1].file_id})
            kind, file_id = "album", (items[0]["id"] if items else "")

        await db.incr("downloads")
        if file_id:
            meta = {"token": token, "hint": res.track_hint, "items": items, "platform": platform}
            await db.put_file(key, kind, file_id, meta)
            await db.put_file("v:" + res.key, kind, file_id, meta)
            first_video = next((i["id"] for i in items if i["t"] == "video"), file_id if kind == "video" else "")
            await db.put_file(f"clip:{token}", "clip", first_video or "-", {"hint": res.track_hint})
    finally:
        if res.workdir:
            shutil.rmtree(res.workdir, ignore_errors=True)


async def _send_video(message: Message, path, caption: str, kb) -> Message:
    info = await media.probe(path)
    thumb = await media.make_thumb(path, path.with_name("thumb.jpg"))
    return await message.answer_video(
        FSInputFile(path),
        width=info["width"] or None,
        height=info["height"] or None,
        duration=int(info["duration"]) or None,
        thumbnail=FSInputFile(thumb) if thumb else None,
        supports_streaming=True,
        caption=caption,
        reply_markup=kb,
        request_timeout=900,
    )
