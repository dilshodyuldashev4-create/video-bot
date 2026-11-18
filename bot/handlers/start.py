from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from ..config import config
from ..db import DB
from ..keyboards import lang_kb
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
