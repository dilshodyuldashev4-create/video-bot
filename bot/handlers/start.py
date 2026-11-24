
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from ..db import DB
from ..keyboards import lang_kb, main_menu
from ..texts import LANGS, menu_labels, t
from ..utils import esc

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, lang: str) -> None:
    if message.chat.type != "private":
        await message.answer(t(lang, "help"))
        return
    await message.answer(t(lang, "start", name=esc(message.from_user.first_name)), reply_markup=main_menu(lang))


@router.message(Command("help"))
@router.message(F.chat.type == "private", F.text.in_(menu_labels("menu_help")))
async def cmd_help(message: Message, lang: str) -> None:
    await message.answer(t(lang, "help"))


@router.message(Command("lang"))
@router.message(F.chat.type == "private", F.text.in_(menu_labels("menu_lang")))
async def cmd_lang(message: Message, lang: str) -> None:
    await message.answer(t(lang, "choose_lang"), reply_markup=lang_kb())


@router.callback_query(F.data.startswith("l:"))
async def cb_lang(call: CallbackQuery, db: DB) -> None:
    new = call.data.split(":", 1)[1]
    if new not in LANGS:
        await call.answer()
        return
    await db.set_lang(call.from_user.id, new)
    await call.message.delete()
    await call.message.answer(t(new, "lang_set"), reply_markup=main_menu(new) if call.message.chat.type == "private" else None)
    await call.answer()


@router.callback_query(F.data == "x")
async def cb_close(call: CallbackQuery) -> None:
    try:
        await call.message.delete()
    except Exception:
        await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
