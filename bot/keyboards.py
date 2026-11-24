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
    shown = query.split("__", 2)[-1] if query.startswith("__") else query  # "__sim__Artist - Song" -> name
    lines = [t(lang, header_key, q=esc(shown), n=len(results), page=page + 1, pages=pages_of(len(results)))]
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


def audio_kb(bot_username: str, lang: str, liked: bool = False, expanded: bool = False) -> InlineKeyboardMarkup:
    """Under every MP3. The effects / ringtone rows open with 🎛 so the keyboard stays short."""
    b = InlineKeyboardButton
    rows = [[b(text=t(lang, "btn_liked" if liked else "btn_like"), callback_data="lk"),
             b(text=t(lang, "btn_lyrics"), callback_data="ly")]]
    if expanded:
        rows += [
            [b(text=t(lang, "btn_up"), callback_data="fx:up"), b(text=t(lang, "btn_slow"), callback_data="fx:slow")],
            [b(text=t(lang, "btn_8d"), callback_data="fx:8d"), b(text=t(lang, "btn_bass"), callback_data="fx:bass")],
            [b(text=t(lang, "btn_minus"), callback_data="fx:minus"),
             b(text=t(lang, "btn_ringtone"), callback_data="rt")],
            [b(text=t(lang, "btn_back"), callback_data="fxb")],
        ]
    else:
        rows += [
            [b(text=t(lang, "btn_similar"), callback_data="sim"), b(text=t(lang, "btn_playlist"), callback_data="pl")],
            [b(text=t(lang, "btn_follow"), callback_data="fol"), b(text=t(lang, "btn_story"), callback_data="st")],
            [b(text=t(lang, "btn_more"), callback_data="fxm")],
        ]
    rows.append(share_row(bot_username, lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def is_expanded(markup: InlineKeyboardMarkup | None) -> bool:
    return bool(markup) and any(btn.callback_data == "fx:up" for row in markup.inline_keyboard for btn in row)


def is_liked_kb(markup: InlineKeyboardMarkup | None) -> bool:
    liked = {t(lg, "btn_liked") for lg in LANGS}
    return bool(markup) and any(btn.text in liked for row in markup.inline_keyboard for btn in row)


def playlist_pick_kb(playlists: list[dict], lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    rows = [[b(text=f"📂 {p['name']} · {p['count']}", callback_data=f"pla:{p['id']}")] for p in playlists[:8]]
    rows.append([b(text=t(lang, "btn_pl_new"), callback_data="pln")])
    rows.append([b(text=t(lang, "btn_back"), callback_data="fxb")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def playlists_kb(playlists: list[dict]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📂 {p['name']} · {p['count']}", callback_data=f"plo:{p['id']}")]
        for p in playlists[:30]])


def playlist_actions_kb(sid: int, total: int, playlist: dict, bot_username: str, lang: str,
                        mine: bool) -> InlineKeyboardMarkup:
    kb = results_kb(sid, total, 0) if total else InlineKeyboardMarkup(inline_keyboard=[])
    link = f"https://t.me/{bot_username}?start=pl_{playlist['code']}"
    share = f"https://t.me/share/url?url={quote(link)}&text={quote(t(lang, 'pl_share_text', name=playlist['name']))}"
    row = [InlineKeyboardButton(text=t(lang, "btn_pl_share"), url=share)]
    if mine:
        row.append(InlineKeyboardButton(text=t(lang, "btn_pl_delete"), callback_data=f"pld:{playlist['id']}"))
    else:
        row.append(InlineKeyboardButton(text=t(lang, "btn_pl_save"), callback_data=f"plc:{playlist['code']}"))
    kb.inline_keyboard.append(row)
    return kb


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
            [KeyboardButton(text=t(lang, "menu_playlists")),
             KeyboardButton(text=t(lang, "menu_wrapped", year=datetime.date.today().year))],
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
