import datetime
from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from .texts import LANGS, t
from .utils import esc, fmt_duration

PAGE_SIZE = 10


def pages_of(total: int) -> int:
    return max(1, (total - 1) // PAGE_SIZE + 1)


def results_text(query: str, results: list[dict], page: int, lang: str, header_key: str = "results_header") -> str:
    start = page * PAGE_SIZE
    lines = [t(lang, header_key, q=esc(query), n=len(results), page=page + 1, pages=pages_of(len(results)))]
    for i, r in enumerate(results[start:start + PAGE_SIZE], start=1):
        dur = fmt_duration(r.get("duration"))
        lines.append(f"<b>{i}.</b> {esc(r['title'])}" + (f" · <b>{dur}</b>" if dur else ""))
    return "\n".join(lines)


def results_kb(search_id: int, total: int, page: int) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    count = min(PAGE_SIZE, total - start)
    nums = [
        InlineKeyboardButton(text=str(i + 1), callback_data=f"t:{search_id}:{start + i}") for i in range(count)
    ]
    rows = [nums[:5], nums[5:]] if count > 5 else [nums]
    last_page = pages_of(total) - 1
    rows.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"p:{search_id}:{page - 1 if page > 0 else last_page}"),
        InlineKeyboardButton(text="❌", callback_data="x"),
        InlineKeyboardButton(text="➡️", callback_data=f"p:{search_id}:{page + 1 if page < last_page else 0}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r])


def share_url(bot_username: str, lang: str) -> str:
    return f"https://t.me/share/url?url={quote(f'https://t.me/{bot_username}')}&text={quote(t(lang, 'share_text'))}"


def share_row(bot_username: str, lang: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text=t(lang, "btn_share"), url=share_url(bot_username, lang)),
        InlineKeyboardButton(text=t(lang, "btn_add_group"), url=f"https://t.me/{bot_username}?startgroup=true"),
    ]


def audio_kb(bot_username: str, lang: str, liked: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text=t(lang, "btn_liked" if liked else "btn_like"), callback_data="lk"),
         b(text=t(lang, "btn_lyrics"), callback_data="ly")],
        [b(text=t(lang, "btn_up"), callback_data="fx:up"),
         b(text=t(lang, "btn_slow"), callback_data="fx:slow")],
        [b(text=t(lang, "btn_8d"), callback_data="fx:8d"),
         b(text=t(lang, "btn_bass"), callback_data="fx:bass")],
        [b(text=t(lang, "btn_minus"), callback_data="fx:minus"),
         b(text=t(lang, "btn_ringtone"), callback_data="rt")],
        share_row(bot_username, lang),
    ])


def video_kb(token: str, bot_username: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_get_song"), callback_data=f"g:{token}")],
        [InlineKeyboardButton(text=t(lang, "btn_note"), callback_data="vn:note"),
         InlineKeyboardButton(text=t(lang, "btn_voice"), callback_data="vn:voice")],
        share_row(bot_username, lang),
    ])


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "menu_top_world")), KeyboardButton(text=t(lang, "menu_top_uz")),
             KeyboardButton(text=t(lang, "menu_top_ru"))],
            [KeyboardButton(text=t(lang, "menu_mood")), KeyboardButton(text=t(lang, "menu_my_music"))],
            [KeyboardButton(text=t(lang, "menu_wrapped", year=datetime.date.today().year))],
            [KeyboardButton(text=t(lang, "menu_help")), KeyboardButton(text=t(lang, "menu_lang"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Pop Smoke Dior · https://…",
    )


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=v, callback_data=f"l:{k}") for k, v in LANGS.items()]]
    )


def link_kb(token: str, lang: str) -> InlineKeyboardMarkup:
    """Choice under a pasted link: video / audio / find the music."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_dl_video"), callback_data=f"dl:v:{token}"),
         InlineKeyboardButton(text=t(lang, "btn_dl_audio"), callback_data=f"dl:a:{token}")],
        [InlineKeyboardButton(text=t(lang, "btn_dl_shazam"), callback_data=f"dl:s:{token}")],
    ])


MOODS = ("sad", "car", "gym", "toy", "chill", "love")


def mood_kb(lang: str) -> InlineKeyboardMarkup:
    b = [InlineKeyboardButton(text=t(lang, f"mood_{m}"), callback_data=f"mood:{m}") for m in MOODS]
    return InlineKeyboardMarkup(inline_keyboard=[b[i:i + 2] for i in range(0, len(b), 2)])


def video_more_kb(token: str, lang: str) -> InlineKeyboardMarkup:
    """Under a video the user sent: turn it into a video note / voice message."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_note"), callback_data=f"vn:note:{token}"),
        InlineKeyboardButton(text=t(lang, "btn_voice"), callback_data=f"vn:voice:{token}")]])
