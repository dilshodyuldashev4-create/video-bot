import asyncio
import shutil

import aiohttp
import yt_dlp
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from ..config import config
from ..db import DB
from ..keyboards import lang_kb
from ..services import downloader
from ..texts import LANGS, t
from ..utils import esc

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, lang: str) -> None:
    if message.chat.type != "private":
        await message.answer(t(lang, "help"))
        return
    await message.answer(t(lang, "start", name=esc(message.from_user.first_name)))


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(t(lang, "help"))


@router.message(Command("lang"))
async def cmd_lang(message: Message, lang: str) -> None:
    await message.answer(t(lang, "choose_lang"), reply_markup=lang_kb())


@router.callback_query(F.data.startswith("l:"))
async def cb_lang(call: CallbackQuery, db: DB) -> None:
    new = call.data.split(":", 1)[1]
    if new not in LANGS:
        await call.answer()
        return
    await db.set_lang(call.from_user.id, new)
    await call.message.edit_text(t(new, "lang_set"))
    await call.answer()


@router.callback_query(F.data == "x")
async def cb_close(call: CallbackQuery) -> None:
    try:
        await call.message.delete()
    except Exception:
        await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: DB, lang: str) -> None:
    if message.from_user.id not in config.admin_ids:
        return
    await message.answer(t(
        lang, "stats",
        users=await db.count_users(),
        downloads=await db.get_stat("downloads"),
        recognitions=await db.get_stat("recognitions"),
    ))


DIAG_TARGETS = [
    ("YouTube", "https://www.youtube.com/watch?v=jNQXAC9IVRw"),
    ("SoundCloud", "scsearch1:Pop Smoke Dior"),
    ("TikTok", "https://www.tiktok.com/@scout2015/video/6718335390845095173"),
]


@router.message(Command("diag"))
async def cmd_diag(message: Message) -> None:
    """Checks what works from this server: /diag (admins only if ADMIN_IDS is set)."""
    if config.admin_ids and message.from_user.id not in config.admin_ids:
        return
    status = await message.answer("🩺 …")
    lines = [
        f"yt-dlp: <code>{yt_dlp.version.__version__}</code>",
        f"deno: {'✅' if shutil.which('deno') else '❌ not installed'}",
        f"cookies: {'✅' if config.cookies else '—'}",
    ]
    if config.pot_url:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{config.pot_url}/ping", timeout=aiohttp.ClientTimeout(total=5)) as r:
                    lines.append(f"PO-token server: {'✅' if r.status == 200 else f'❌ HTTP {r.status}'}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"PO-token server: ❌ {type(e).__name__}")
    else:
        lines.append("PO-token server: — (POT_PROVIDER_URL not set)")
    lines.append(f"proxy (WARP): {'set' if config.proxy else '— (PROXY_URL not set)'}")
    lines.append("")

    async def check(name: str, url: str) -> str:
        direct, proxied = await asyncio.gather(
            downloader.check_route_async(url, False),
            downloader.check_route_async(url, True) if config.proxy else asyncio.sleep(0, "—"),
        )
        fmt = lambda r: "✅" if r is None else ("—" if r == "—" else f"❌ {esc(r)}")
        return f"<b>{name}</b>\n  direct: {fmt(direct)}\n  via proxy: {fmt(proxied)}"

    lines += await asyncio.gather(*(check(n, u) for n, u in DIAG_TARGETS))
    await status.edit_text("\n".join(lines), disable_web_page_preview=True)
