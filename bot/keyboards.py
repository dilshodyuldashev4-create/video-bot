from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .texts import LANGS, t
from .utils import esc, fmt_duration

PAGE_SIZE = 10


def results_text(query: str, results: list[dict], page: int, lang: str) -> str:
    start = page * PAGE_SIZE
    lines = [t(lang, "results_header", q=esc(query))]
    for i, r in enumerate(results[start:start + PAGE_SIZE], start=1):
        dur = fmt_duration(r.get("duration"))
        lines.append(f"{i}. {esc(r['title'])}" + (f" <b>{dur}</b>" if dur else ""))
    return "\n".join(lines)


def results_kb(search_id: int, total: int, page: int) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    count = min(PAGE_SIZE, total - start)
    nums = [
        InlineKeyboardButton(text=str(i + 1), callback_data=f"t:{search_id}:{start + i}") for i in range(count)
    ]
    rows = [nums[:5], nums[5:]] if count > 5 else [nums]
    last_page = (total - 1) // PAGE_SIZE
    rows.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"p:{search_id}:{page - 1 if page > 0 else last_page}"),
        InlineKeyboardButton(text="❌", callback_data="x"),
        InlineKeyboardButton(text="➡️", callback_data=f"p:{search_id}:{page + 1 if page < last_page else 0}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r])


def add_group_row(bot_username: str, lang: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=t(lang, "btn_add_group"), url=f"https://t.me/{bot_username}?startgroup=true")]


def audio_kb(bot_username: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[add_group_row(bot_username, lang)])


def video_kb(token: str, bot_username: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_get_song"), callback_data=f"g:{token}")],
        add_group_row(bot_username, lang),
    ])


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=v, callback_data=f"l:{k}") for k, v in LANGS.items()]]
    )
