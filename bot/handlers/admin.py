"""👑 Admin panel: /admin

Who is an admin: ADMIN_IDS from .env, plus admins added from the panel.
If there are no admins at all yet, the first person to send /admin becomes the owner.
"""
import asyncio
import logging
import shutil

import aiohttp
import yt_dlp
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from ..config import config
from ..db import DB
from ..services import cobalt, downloader, mp3sites, tiktok, ytalt
from ..texts import LANGS, LINE
from ..utils import esc

log = logging.getLogger(__name__)
router = Router(name="admin")

BROADCAST_DELAY = 0.05  # ~20 messages/second, below Telegram's limit


class Broadcast(StatesGroup):
    waiting_message = State()


async def is_admin(db: DB, user_id: int) -> bool:
    return user_id in config.admin_ids or user_id in await db.admin_ids()


def panel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="📊 Статистика", callback_data="adm:stats"),
         b(text="📢 Рассылка", callback_data="adm:bc")],
        [b(text="🔥 Топ запросов", callback_data="adm:top"),
         b(text="🩺 Диагностика", callback_data="adm:diag")],
        [b(text="👑 Админы", callback_data="adm:admins")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:home")]])


PANEL_TEXT = "👑 <b>Админ-панель</b>\n" + LINE + "\nВыбери, что сделать 👇"


@router.message(Command("admin"))
async def cmd_admin(message: Message, db: DB) -> None:
    uid = message.from_user.id
    if not await is_admin(db, uid):
        if config.admin_ids or await db.admin_ids():
            return  # silently ignore strangers
        await db.add_admin(uid)  # first /admin on a fresh bot = owner
        await message.answer("👑 Ты теперь владелец бота. Админ-панель доступна только тебе.")
    await message.answer(PANEL_TEXT, reply_markup=panel_kb())


async def _guard(call: CallbackQuery, db: DB) -> bool:
    if await is_admin(db, call.from_user.id):
        return True
    await call.answer("⛔️", show_alert=True)
    return False


async def _show(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb or back_kb(), disable_web_page_preview=True)
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(F.data == "adm:home")
async def cb_home(call: CallbackQuery, db: DB, state: FSMContext) -> None:
    if await _guard(call, db):
        await state.clear()
        await _show(call, PANEL_TEXT, panel_kb())


# ---------------------------------------------------------------- stats

async def stats_text(db: DB) -> str:
    s = await db.user_stats()
    langs = " · ".join(f"{LANGS.get(k, k).split()[0]} {v}" for k, v in sorted(s["langs"].items(), key=lambda x: -x[1]))
    return (
        "📊 <b>Статистика</b>\n" + LINE + "\n"
        f"👥 Всего пользователей: <b>{s['total']}</b>\n"
        f"🆕 Новых за 24 ч / 7 дней: <b>{s['new_day']}</b> / <b>{s['new_week']}</b>\n"
        f"🔥 Активных за 24 ч / 7 дней: <b>{s['active_day']}</b> / <b>{s['active_week']}</b>\n"
        f"🚫 Заблокировали бота: <b>{s['blocked']}</b>\n"
        f"🌐 Языки: {langs or '—'}\n" + LINE + "\n"
        f"📥 Скачиваний: <b>{await db.get_stat('downloads')}</b>\n"
        f"🔍 Распознаваний: <b>{await db.get_stat('recognitions')}</b>\n"
        f"🔎 Поисков за 7 дней: <b>{s['searches_week']}</b>\n"
        f"❤️ Лайков: <b>{s['likes']}</b>"
    )


@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery, db: DB) -> None:
    if await _guard(call, db):
        await _show(call, await stats_text(db))


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: DB) -> None:
    if await is_admin(db, message.from_user.id):
        await message.answer(await stats_text(db))


@router.callback_query(F.data == "adm:top")
async def cb_top(call: CallbackQuery, db: DB) -> None:
    if not await _guard(call, db):
        return
    rows = await db.top_queries()
    lines = ["🔥 <b>Топ запросов за 7 дней</b>", LINE]
    lines += [f"<b>{i}.</b> {esc(q)} · {c}" for i, (q, c) in enumerate(rows, 1)] or ["Пока пусто"]
    await _show(call, "\n".join(lines))


# ---------------------------------------------------------------- admins

@router.callback_query(F.data == "adm:admins")
async def cb_admins(call: CallbackQuery, db: DB) -> None:
    if not await _guard(call, db):
        return
    ids = sorted(config.admin_ids | await db.admin_ids())
    lines = ["👑 <b>Админы</b>", LINE]
    lines += [f"• <code>{i}</code>" + (" (из .env)" if i in config.admin_ids else "") for i in ids]
    lines += [LINE, f"Твой ID: <code>{call.from_user.id}</code>",
              "Добавить: <code>/addadmin ID</code>", "Убрать: <code>/deladmin ID</code>",
              "<i>ID человека можно узнать, переслав его сообщение боту @userinfobot</i>"]
    await _show(call, "\n".join(lines))


@router.message(Command("addadmin", "deladmin"))
async def cmd_edit_admin(message: Message, command: CommandObject, db: DB) -> None:
    if not await is_admin(db, message.from_user.id):
        return
    arg = (command.args or "").strip()
    if not arg.lstrip("-").isdigit():
        await message.answer(f"Напиши так: <code>/{command.command} 123456789</code>")
        return
    uid = int(arg)
    if command.command == "addadmin":
        await db.add_admin(uid)
        await message.answer(f"✅ <code>{uid}</code> теперь админ")
    else:
        if uid == message.from_user.id and len(config.admin_ids | await db.admin_ids()) <= 1:
            await message.answer("⚠️ Нельзя убрать единственного админа.")
            return
        await db.remove_admin(uid)
        note = " (он в ADMIN_IDS в .env, оттуда убери вручную)" if uid in config.admin_ids else ""
        await message.answer(f"✅ <code>{uid}</code> больше не админ{note}")


# ---------------------------------------------------------------- broadcast

@router.callback_query(F.data == "adm:bc")
async def cb_broadcast(call: CallbackQuery, db: DB, state: FSMContext) -> None:
    if not await _guard(call, db):
        return
    await state.set_state(Broadcast.waiting_message)
    n = len(await db.broadcast_ids())
    await _show(call, "📢 <b>Рассылка</b>\n" + LINE + f"\nПолучателей: <b>{n}</b>\n\n"
                "Пришли сообщение, которое нужно разослать: текст, фото, видео, аудио, "
                "можно с форматированием. Я покажу, как оно выглядит, и спрошу подтверждение.\n\n/cancel — отмена")


@router.message(Broadcast.waiting_message, Command("cancel"))
async def cancel_broadcast(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("❌ Рассылка отменена", reply_markup=back_kb())


@router.message(Broadcast.waiting_message, ~F.text.startswith("/"))
async def on_broadcast_message(message: Message, db: DB, state: FSMContext) -> None:
    if not await is_admin(db, message.from_user.id):
        await state.clear()
        return
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id)
    n = len(await db.broadcast_ids())
    await message.copy_to(message.chat.id, reply_markup=message.reply_markup)
    await message.answer(
        f"👆 Так увидят сообщение пользователи. Отправить <b>{n}</b> пользователям?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"✅ Отправить ({n})", callback_data="adm:bc_go"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="adm:home"),
        ]]),
    )


@router.callback_query(F.data == "adm:bc_go")
async def cb_broadcast_go(call: CallbackQuery, bot: Bot, db: DB, state: FSMContext) -> None:
    if not await _guard(call, db):
        return
    data = await state.get_data()
    await state.clear()
    if not data.get("message_id"):
        await _show(call, "⌛️ Сообщение для рассылки потерялось, начни заново.")
        return
    await call.answer("🚀")
    progress = await call.message.edit_text("📢 Рассылка началась…")
    asyncio.create_task(run_broadcast(bot, db, data["chat_id"], data["message_id"], progress))


async def run_broadcast(bot: Bot, db: DB, from_chat: int, message_id: int, progress: Message | bool) -> dict:
    ids = await db.broadcast_ids()
    sent = failed = blocked = 0
    for i, uid in enumerate(ids, 1):
        for attempt in range(3):
            try:
                await bot.copy_message(uid, from_chat, message_id)
                sent += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:  # user blocked the bot / deleted account
                blocked += 1
                await db.set_blocked(uid)
                break
            except Exception:  # noqa: BLE001
                failed += 1
                break
        await asyncio.sleep(BROADCAST_DELAY)
        if isinstance(progress, Message) and i % 200 == 0:
            try:
                await progress.edit_text(f"📢 Рассылка… {i}/{len(ids)}")
            except TelegramBadRequest:
                pass
    report = {"sent": sent, "blocked": blocked, "failed": failed, "total": len(ids)}
    if isinstance(progress, Message):
        try:
            await progress.edit_text(
                "📢 <b>Рассылка завершена</b>\n" + LINE + f"\n✅ Доставлено: <b>{sent}</b>\n"
                f"🚫 Заблокировали бота: <b>{blocked}</b>\n⚠️ Ошибки: <b>{failed}</b>",
                reply_markup=back_kb())
        except TelegramBadRequest:
            pass
    return report


# ---------------------------------------------------------------- diagnostics

DIAG_TIKTOK = "https://www.tiktok.com/@scout2015/video/6718335390845095173"
DIAG_TARGETS = [
    ("YouTube", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
    ("SoundCloud", "scsearch1:Pop Smoke Dior"),
    ("TikTok", "https://www.tiktok.com/@scout2015/video/6718335390845095173"),
]


async def diag_text() -> str:
    lines = [
        "🩺 <b>Диагностика</b>", LINE,
        f"yt-dlp: <code>{yt_dlp.version.__version__}</code>",
        f"deno: {'✅' if shutil.which('deno') else '❌ not installed'}",
        f"cookies: {'✅ ' + esc(config.cookies) if config.cookies else '—'}",
    ]
    if config.pot_url:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{config.pot_url}/ping", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    lines.append(f"PO-token server: {'✅' if r.status == 200 else f'❌ HTTP {r.status}'}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"PO-token server: ❌ {type(e).__name__}")
    else:
        lines.append("PO-token server: —")
    lines.append(f"proxy (WARP): {'set' if config.proxy else '—'}")
    lines.append("")

    async def check(name: str, url: str) -> str:
        direct, proxied = await asyncio.gather(
            downloader.check_route_async(url, False),
            downloader.check_route_async(url, True) if config.proxy else asyncio.sleep(0, "—"),
        )
        fmt = lambda r: "✅" if r is None else ("—" if r == "—" else f"❌ {esc(r)}")
        text = f"<b>{name}</b>\n  direct: {fmt(direct)}\n  via proxy: {fmt(proxied)}"
        if name == "YouTube" and config.yt_proxy:
            text += f"\n  via YT_PROXY_URL: {fmt(await downloader.check_route_async(url, config.yt_proxy))}"
        return text

    lines += await asyncio.gather(*(check(n, u) for n, u in DIAG_TARGETS))

    def sites() -> str:
        try:
            found, base = mp3sites.search_sync("Uzboom")
            return f"✅ {esc(base)} ({len(found)} треков)" if found else f"⚠️ {esc(base)}: 0 треков"
        except Exception as e:  # noqa: BLE001
            return f"❌ {esc(str(e)[:150])}"
    lines.append(f"<b>MP3-каталог</b>: {await asyncio.to_thread(sites)}")

    def alt() -> str:
        try:
            ytalt.reset_pause()
            info = ytalt.fetch_info("jNQXAC9IVRw")
            return f"✅ {esc(info.source)}"
        except Exception as e:  # noqa: BLE001
            return f"❌ {esc(str(e)[:300])}"
    def cob() -> str:
        try:
            cobalt.reset_pause()
            apis = cobalt.instances()
            if not apis:
                return "❌ нет публичных серверов"
            cobalt.fetch("https://www.youtube.com/watch?v=jNQXAC9IVRw", audio=True)
            return f"✅ {esc(cobalt._good[0])} (из {len(apis)})"
        except Exception as e:  # noqa: BLE001
            return f"❌ {esc(str(e)[:300])}"
    lines.append(f"<b>YouTube через cobalt</b>: {await asyncio.to_thread(cob)}")
    lines.append(f"<b>YouTube через Invidious/Piped</b>: {await asyncio.to_thread(alt)}")
    def tt() -> str:
        try:
            post = tiktok.fetch(DIAG_TIKTOK)
            return "✅" if post.video or post.images else "⚠️ no video"
        except Exception as e:  # noqa: BLE001
            return f"❌ {esc(str(e)[:150])}"
    lines.append(f"<b>TikTok через tikwm</b>: {await asyncio.to_thread(tt)}")
    if downloader.youtube_blocked():
        lines.append("⚠️ YouTube сейчас блокирует сервер: MP3 берутся из других источников")
    return "\n".join(lines)


@router.callback_query(F.data == "adm:diag")
async def cb_diag(call: CallbackQuery, db: DB) -> None:
    if not await _guard(call, db):
        return
    await call.answer("🩺")
    try:
        await call.message.edit_text("🩺 Проверяю…")
    except TelegramBadRequest:
        pass
    await _show(call, await diag_text())


@router.message(Command("diag"))
async def cmd_diag(message: Message, db: DB) -> None:
    if not await is_admin(db, message.from_user.id):
        return
    status = await message.answer("🩺 …")
    await status.edit_text(await diag_text(), disable_web_page_preview=True)


# ---------------------------------------------------------------- YouTube cookies (sent as a file)

COOKIES_HELP = (
    "🍪 <b>Cookies для YouTube</b>\n" + LINE + "\n"
    "Пришли мне файл <code>cookies.txt</code> (формат Netscape) от запасного Google-аккаунта, "
    "и я сразу начну качать YouTube с ним.\n\n"
    "/cookies — статус\n/cookies off — удалить cookies"
)


def _looks_like_cookies(data: bytes) -> bool:
    text = data[:200_000].decode("utf-8", "replace")
    return ".youtube.com" in text and "\t" in text


@router.message(Command("cookies"))
async def cmd_cookies(message: Message, db: DB, command: CommandObject) -> None:
    if not await is_admin(db, message.from_user.id):
        return
    if (command.args or "").strip().lower() in ("off", "delete", "del"):
        config.cookies_path.unlink(missing_ok=True)
        await message.answer("🗑 Cookies удалены.")
        return
    state = f"✅ сейчас используются: <code>{esc(config.cookies)}</code>" if config.cookies else "— сейчас нет"
    await message.answer(f"{COOKIES_HELP}\n\n{state}")


@router.message(F.document & F.document.file_name.lower().endswith(".txt"))
async def on_cookies_file(message: Message, bot: Bot, db: DB) -> None:
    if not await is_admin(db, message.from_user.id):
        return
    if message.document.file_size and message.document.file_size > 2_000_000:
        await message.answer("❌ Файл слишком большой для cookies.")
        return
    tmp = config.data_dir / "cookies.upload"
    await bot.download(message.document.file_id, destination=tmp)
    data = tmp.read_bytes()
    tmp.unlink(missing_ok=True)
    if not _looks_like_cookies(data):
        await message.answer("❌ Это не похоже на cookies YouTube (нужен cookies.txt в формате Netscape с .youtube.com).")
        return
    config.cookies_path.write_bytes(data)
    config.cookies_path.chmod(0o600)
    downloader.reset_youtube_block()
    status = await message.answer("✅ Cookies сохранены. Проверяю YouTube…")
    err = await downloader.check_route_async(DIAG_TARGETS[0][1], False)
    if err and config.proxy:
        err = await downloader.check_route_async(DIAG_TARGETS[0][1], True)
    await status.edit_text("✅ Cookies сохранены, YouTube работает!" if err is None
                           else f"⚠️ Cookies сохранены, но YouTube пока отвечает:\n<code>{esc(err)}</code>")
