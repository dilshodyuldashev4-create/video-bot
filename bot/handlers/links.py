"""YouTube / Instagram / TikTok link -> video in good quality + "download the song" button."""
import logging
import shutil
import uuid

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, Message
from aiogram.utils.media_group import MediaGroupBuilder

from ..common import bot_username, user_lock
from ..config import config
from ..db import DB
from ..keyboards import video_kb
from ..services import downloader, media
from ..texts import t
from ..utils import URL_RE, canonical_key, detect_platform, extract_url

log = logging.getLogger(__name__)
router = Router(name="links")

PHOTO_EXT = (".jpg", ".jpeg", ".png", ".webp")


def clips_dir():
    d = config.data_dir / "clips"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _send_cached(message: Message, cached: tuple, lang: str, username: str) -> bool:
    kind, file_id, meta = cached
    token = meta.get("token") or ""
    caption = t(lang, "video_caption", bot=username)
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


@router.message(F.text.regexp(URL_RE) | F.caption.regexp(URL_RE))
async def on_link(message: Message, bot: Bot, db: DB, lang: str) -> None:
    url = extract_url(message.text or message.caption)
    platform = detect_platform(url) if url else None
    private = message.chat.type == "private"
    if not platform:
        if private:
            await message.reply(t(lang, "unsupported_link"))
        return

    async with user_lock(message.from_user.id if message.from_user else message.chat.id) as ok:
        if not ok:
            if private:
                await message.reply(t(lang, "busy"))
            return
        username = await bot_username(bot)
        status = await message.reply(t(lang, "downloading"))
        try:
            await _handle(message, bot, db, lang, username, url, platform)
        except downloader.TooBig:
            await message.reply(t(lang, "too_big"))
        except downloader.DownloadFailed:
            log.warning("download failed: %s", url, exc_info=True)
            await message.reply(t(lang, "dl_failed"))
        except Exception:
            log.exception("link handler failed: %s", url)
            await message.reply(t(lang, "error"))
        finally:
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


async def _handle(message: Message, bot: Bot, db: DB, lang: str, username: str, url: str, platform: str) -> None:
    key = "v:" + canonical_key(url, platform)
    cached = await db.get_file(key)
    if cached and await _send_cached(message, cached, lang, username):
        await db.incr("downloads")
        return

    res = await downloader.download_video(url, platform)
    try:
        token = uuid.uuid4().hex[:16]
        caption = t(lang, "video_caption", bot=username)
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
            meta = {"token": token, "hint": res.track_hint, "items": items}
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
