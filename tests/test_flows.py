"""End-to-end handler flows with a fake Telegram API (no network)."""
import datetime
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import (AnswerCallbackQuery, DeleteMessage, EditMessageText, GetMe, SendAudio,
                             SendMediaGroup, SendMessage, SendPhoto, SendVideo, TelegramMethod)
from aiogram.types import Audio, CallbackQuery, Chat, Message, PhotoSize, Update, User, Video

from bot.__main__ import build_dispatcher
from bot.db import DB
from bot.handlers import recognize as rec_handler
from bot.services import downloader, recognizer

USER = User(id=42, is_bot=False, first_name="Dilshod", language_code="ru")
CHAT = Chat(id=42, type="private")
NOW = datetime.datetime.now()


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []
        self.n = 100

    def _msg(self, **kw) -> Message:
        self.n += 1
        return Message(message_id=self.n, date=NOW, chat=CHAT, **kw)

    async def make_request(self, bot, method, timeout=None):
        res = await self._make(bot, method)
        if isinstance(res, list):
            return [r.as_(bot) for r in res]
        return res.as_(bot) if hasattr(res, "as_") else res

    async def _make(self, bot, method):
        self.calls.append(method)
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="Bot", username="TestMusicBot")
        if isinstance(method, (SendMessage, EditMessageText)):
            return self._msg(text=method.text)
        if isinstance(method, SendAudio):
            return self._msg(audio=Audio(file_id=f"AUD{self.n}", file_unique_id="u", duration=30))
        if isinstance(method, SendVideo):
            return self._msg(video=Video(file_id=f"VID{self.n}", file_unique_id="u", width=720, height=1280,
                                         duration=30))
        if isinstance(method, SendPhoto):
            return self._msg(photo=[PhotoSize(file_id="PH", file_unique_id="u", width=1, height=1)])
        if isinstance(method, SendMediaGroup):
            return [self._msg(video=Video(file_id=f"V{i}", file_unique_id="u", width=1, height=1, duration=1))
                    for i, _ in enumerate(method.media)]
        if isinstance(method, (DeleteMessage, AnswerCallbackQuery)):
            return True
        return True

    async def close(self):
        pass

    async def stream_content(self, *a, **k):
        yield b""

    def of(self, cls):
        return [c for c in self.calls if isinstance(c, cls)]


@pytest.fixture
async def env(data_dir):
    session = FakeSession()
    bot = Bot("1:test", session=session)
    db = DB(data_dir / "t.sqlite3")
    await db.connect()
    from bot.handlers import admin, inline, library, links, recognize, search, start, tools
    for r in (admin.router, inline.router, library.router, links.router, recognize.router, search.router,
              start.router, tools.router):
        r._parent_router = None  # allow a fresh Dispatcher per test
    dp = build_dispatcher(db)
    session.dp, session.bot = dp, bot  # for tests that feed other update types
    counter = iter(range(1, 10_000))

    async def send_text(text):
        msg = Message(message_id=next(counter), date=NOW, chat=CHAT, from_user=USER, text=text).as_(bot)
        await dp.feed_update(bot, Update(update_id=next(counter), message=msg).as_(bot))

    async def send_media(**kw):
        msg = Message(message_id=next(counter), date=NOW, chat=CHAT, from_user=USER, **kw).as_(bot)
        await dp.feed_update(bot, Update(update_id=next(counter), message=msg).as_(bot))

    async def press(data, message=None):
        message = (message or Message(message_id=1, date=NOW, chat=CHAT, text="x")).as_(bot)
        cq = CallbackQuery(id=str(next(counter)), from_user=USER, chat_instance="c", data=data, message=message).as_(bot)
        await dp.feed_update(bot, Update(update_id=next(counter), callback_query=cq).as_(bot))

    yield session, db, send_text, press, send_media
    await db.close()


@pytest.fixture
def fake_audio(monkeypatch, http_base):
    calls = []
    real = downloader.download_audio

    async def fake(video_id, url=None):
        calls.append(video_id)
        return await real(video_id, url=f"{http_base}/clip.mp4")

    monkeypatch.setattr(downloader, "download_audio", fake)
    return calls


async def test_search_list_paging_and_mp3(env, monkeypatch, fake_audio):
    session, db, send_text, press, _ = env
    tracks = [downloader.Track(id=f"id{i:09d}", title=f"POP SMOKE - DIOR {i}", duration=173) for i in range(25)]

    async def fake_search(q, limit=30):
        assert q == "Dior"
        return tracks

    monkeypatch.setattr(downloader, "search", fake_search)
    await send_text("Dior")
    edit = session.of(EditMessageText)[-1]
    assert "<b>1.</b> POP SMOKE - DIOR 0 · <b>2:53</b>" in edit.text and "<b>10.</b> POP SMOKE - DIOR 9" in edit.text
    assert "стр. 1/3" in edit.text
    rows = edit.reply_markup.inline_keyboard
    assert len(rows[0]) == 5 and len(rows[1]) == 5

    await press("p:1:1")
    assert "<b>1.</b> POP SMOKE - DIOR 10" in session.of(EditMessageText)[-1].text

    await press("t:1:3")
    audio = session.of(SendAudio)[-1]
    assert fake_audio == ["id000000003"]
    assert audio.caption.startswith("🎧") and "@TestMusicBot" in audio.caption
    kb = audio.reply_markup.inline_keyboard
    assert kb[0][0].callback_data == "lk" and kb[0][0].style == "danger"
    assert [b.callback_data for b in kb[0]] == ["lk", "ly"]
    assert [b.callback_data for b in kb[1]] == ["fx:up", "fx:slow"]
    assert [b.callback_data for b in kb[2]] == ["fx:8d", "fx:bass"]
    assert [b.callback_data for b in kb[3]] == ["fx:minus", "rt"]
    assert kb[4][1].url == "https://t.me/TestMusicBot?startgroup=true"
    assert "POP SMOKE" in audio.caption or "clip" in audio.caption

    # second time: sent instantly from the file_id cache, no new download
    await press("t:1:3")
    assert fake_audio == ["id000000003"]
    assert isinstance(session.of(SendAudio)[-1].audio, str)


async def test_nothing_found(env, monkeypatch):
    session, _, send_text, _, _ = env

    async def empty(q, limit=30):
        return []

    monkeypatch.setattr(downloader, "search", empty)
    await send_text("asdkjhaskdjh")
    assert "ничего нет" in session.of(EditMessageText)[-1].text


async def test_link_video_then_song_button(env, monkeypatch, http_base, fake_audio):
    session, db, send_text, press, _ = env
    real_dl = downloader.download_video

    async def fake_video(url, platform):
        assert platform == "tiktok"
        return await real_dl(f"{http_base}/clip.mp4", platform)

    monkeypatch.setattr(downloader, "download_video", fake_video)
    await send_text("https://vm.tiktok.com/ZMabc123/")
    choice = session.of(SendMessage)[-1]
    assert "TikTok" in choice.text
    buttons = [b.callback_data for row in choice.reply_markup.inline_keyboard for b in row]
    assert [b[:5] for b in buttons] == ["dl:v:", "dl:a:", "dl:s:"]
    assert not session.of(SendVideo)  # nothing is downloaded before the user chooses
    await press(buttons[0])
    video = session.of(SendVideo)[-1]
    assert (video.width, video.height, video.supports_streaming) == (720, 1280, True)
    assert video.thumbnail is not None
    btn = video.reply_markup.inline_keyboard[0][0]
    assert btn.callback_data.startswith("g:")

    # same link again -> cached file_id, no second download
    n_before = len(session.of(SendVideo))
    monkeypatch.setattr(downloader, "download_video", None)
    await send_text("https://vm.tiktok.com/ZMabc123/?lang=ru")
    again = session.of(SendMessage)[-1].reply_markup.inline_keyboard[0][0].callback_data
    await press(again)
    assert len(session.of(SendVideo)) == n_before + 1
    assert isinstance(session.of(SendVideo)[-1].video, str)  # file_id, not a re-upload

    async def fake_rec(path):
        assert Path(path).exists()
        return recognizer.Song("Dior", "Pop Smoke")

    async def fake_search(q, limit=30):
        return [downloader.Track(id="oorVWW9ywG0", title="POP SMOKE - DIOR (OFFICIAL VIDEO)")]

    monkeypatch.setattr(recognizer, "recognize", fake_rec)
    monkeypatch.setattr(downloader, "search", fake_search)
    await press(btn.callback_data)
    audio = session.of(SendAudio)[-1]
    assert "Найдено по звуку" in audio.caption
    card = session.of(SendMessage)[-1]
    assert "Shazam нашёл" in card.text and "Dior" in card.text and "Pop Smoke" in card.text
    edits = session.of(EditMessageText)
    assert edits and "Качаю MP3" not in edits[-1].text  # card finalised after the MP3
    assert fake_audio == ["oorVWW9ywG0"]


async def test_unsupported_link(env):
    session, _, send_text, _, _ = env
    await send_text("https://example.com/x")
    assert "не знаю" in session.of(SendMessage)[-1].text


async def test_voice_recognition_and_failure(env, monkeypatch, media_dir, fake_audio, data_dir):
    session, _, _, _, send_media = env

    async def fake_fetch(bot, file_id, size):
        d = data_dir / "in"
        d.mkdir(exist_ok=True)
        shutil.copy(media_dir / "clip.mp4", d / "input")
        return d / "input"

    monkeypatch.setattr(rec_handler, "_fetch", fake_fetch)
    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(None))
    await send_media(video=Video(file_id="x", file_unique_id="u", width=1, height=1, duration=30))
    texts = [m.text for m in session.of(SendMessage)]
    assert any("Не смог узнать" in x for x in texts)
    assert session.of(SendMessage)[-1].reply_markup.inline_keyboard[0][0].callback_data.startswith("vn:note:")

    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(recognizer.Song("Dior", "Pop Smoke")))
    monkeypatch.setattr(downloader, "search", lambda q, limit=30: _async([downloader.Track(id="abc", title="Dior")]))
    from aiogram.types import Voice
    await send_media(voice=Voice(file_id="v", file_unique_id="u", duration=10))
    assert session.of(SendAudio)
    assert "Pop Smoke" in session.of(SendMessage)[-1].text


async def test_language_switch(env):
    session, db, send_text, press, _ = env
    await press("l:uz")
    sent = session.of(SendMessage)[-1]
    assert "O'zbekcha" in sent.text
    assert sent.reply_markup.keyboard[0][0].text == "🔥 Hafta topi"
    assert sent.reply_markup.keyboard[1][1].text == "❤️ Mening musiqam"
    await send_text("/start")
    assert "Salom" in session.of(SendMessage)[-1].text


async def _async(v):
    return v


async def test_youtube_blocked_falls_back_to_soundcloud(env, monkeypatch, http_base):
    session, db, send_text, press, _ = env

    async def fake_search(q, limit=30):
        return [downloader.Track(id="U3kf72Zw3yA", title="POP SMOKE - DIOR (OFFICIAL VIDEO)", duration=173)]

    async def blocked(video_id, url=None):
        raise downloader.DownloadFailed("Sign in to confirm you're not a bot")

    sc_queries = []
    real = downloader.download_audio_soundcloud

    async def fake_sc(query):
        sc_queries.append(query)
        return await downloader._fetch_audio(f"{http_base}/clip.mp4")

    monkeypatch.setattr(downloader, "search", fake_search)
    monkeypatch.setattr(downloader, "download_audio", blocked)
    monkeypatch.setattr(downloader, "download_audio_soundcloud", fake_sc)
    await send_text("Dior")
    await press("t:1:0")
    assert sc_queries == ["POP SMOKE - DIOR"]
    assert session.of(SendAudio), "MP3 must still be sent"
    assert real is not None


async def test_track_failed_message_when_everything_blocked(env, monkeypatch):
    session, db, send_text, press, _ = env

    async def fake_search(q, limit=30):
        return [downloader.Track(id="U3kf72Zw3yA", title="POP SMOKE - DIOR", duration=173)]

    async def blocked(*a, **k):
        raise downloader.DownloadFailed("blocked")

    monkeypatch.setattr(downloader, "search", fake_search)
    monkeypatch.setattr(downloader, "download_audio", blocked)
    monkeypatch.setattr(downloader, "download_audio_soundcloud", blocked)
    await send_text("Dior")
    await press("t:1:0")
    assert "другой номер" in session.of(SendMessage)[-1].text


async def test_likes_and_my_music(env):
    session, db, send_text, press, _ = env
    await send_text("/mymusic")
    assert "пока пусто" in session.of(SendMessage)[-1].text

    audio_msg = Message(message_id=500, date=NOW, chat=CHAT,
                        audio=Audio(file_id="AUDFILE", file_unique_id="uniq1", duration=173,
                                    performer="Pop Smoke", title="Dior"))
    await press("lk", message=audio_msg)
    from aiogram.methods import EditMessageReplyMarkup
    kb = session.of(EditMessageReplyMarkup)[-1].reply_markup
    assert kb.inline_keyboard[0][0].text == "💖 В избранном"
    assert "t.me/share/url" in kb.inline_keyboard[4][0].url

    await send_text("❤️ Моя музыка")  # reply-keyboard button
    lst = session.of(SendMessage)[-1]
    assert "Моя музыка" in lst.text and "Pop Smoke - Dior" in lst.text
    sid = lst.reply_markup.inline_keyboard[0][0].callback_data.split(":")[1]
    await press(f"t:{sid}:0")
    sent = session.of(SendAudio)[-1]
    assert sent.audio == "AUDFILE" and "Dior" in sent.caption

    await press("lk", message=audio_msg)  # unlike
    assert session.of(EditMessageReplyMarkup)[-1].reply_markup.inline_keyboard[0][0].text == "❤️ В избранное"
    await send_text("/mymusic")
    assert "пока пусто" in session.of(SendMessage)[-1].text


async def test_shazam_card_with_cover(env, monkeypatch, media_dir, data_dir, fake_audio):
    session, _, _, _, send_media = env

    async def fake_fetch(bot, file_id, size):
        d = data_dir / "in2"
        d.mkdir(exist_ok=True)
        shutil.copy(media_dir / "clip.mp4", d / "input")
        return d / "input"

    monkeypatch.setattr(rec_handler, "_fetch", fake_fetch)
    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(recognizer.Song(
        "Dior", "Pop Smoke", cover="https://is1.example/cover.jpg", shazam_url="https://www.shazam.com/track/1")))
    monkeypatch.setattr(downloader, "search", lambda q, limit=30: _async([downloader.Track(id="cov", title="Dior")]))
    await send_media(video=Video(file_id="x", file_unique_id="u", width=1, height=1, duration=30))
    photo = session.of(SendPhoto)[-1]
    assert photo.photo == "https://is1.example/cover.jpg" and "Shazam нашёл" in photo.caption
    assert photo.reply_markup is None  # no "Open in Shazam" button
    from aiogram.methods import EditMessageCaption, SetMessageReaction
    assert "Качаю MP3" not in session.of(EditMessageCaption)[-1].caption
    reactions = [r.reaction[0].emoji for r in session.of(SetMessageReaction)]
    assert reactions[:1] == ["👀"] and reactions[-1] == "🔥"


async def test_charts_menu_and_pick(env, monkeypatch, fake_audio):
    session, db, send_text, press, _ = env
    from bot.services import charts

    async def fake_chart(kind):
        assert kind == "uz"
        return [charts._item("Shahzoda", "Hayot"), charts._item("Pop Smoke", "Dior")]

    monkeypatch.setattr(charts, "get_chart", fake_chart)
    found = []

    async def fake_search(q, limit=30):
        found.append(q)
        return [downloader.Track(id="uzhit", title="Pop Smoke - Dior")]

    monkeypatch.setattr(downloader, "search", fake_search)
    await send_text("🇺🇿 Топ UZ")
    edit = session.of(EditMessageText)[-1]
    assert "Топ Узбекистана" in edit.text and "<b>2.</b> Pop Smoke - Dior" in edit.text
    sid = edit.reply_markup.inline_keyboard[0][0].callback_data.split(":")[1]
    await press(f"t:{sid}:1")
    assert found == ["Pop Smoke - Dior"] and fake_audio == ["uzhit"]
    await press(f"p:{sid}:0")  # paging keeps the chart header (same page -> not modified is fine)


async def test_chart_falls_back_to_youtube(monkeypatch):
    from bot.services import charts
    charts._cache.clear()

    async def broken(kind):
        raise RuntimeError("Country not found, check the country code: UZ")

    async def yt(q, limit=30):
        assert "uzbek" in q
        return [downloader.Track(id="a1", title="Shahzoda - Hayot (Official Video)", duration=200)]

    monkeypatch.setattr(charts, "_shazam_chart", broken)
    monkeypatch.setattr(downloader, "search", yt)
    items = await charts.get_chart("uz")
    assert items == [{"id": "a1", "title": "Shahzoda - Hayot", "duration": 200}]


async def test_speed_up_and_slowed(env, monkeypatch, http_base, data_dir):
    session, db, send_text, press, _ = env
    # a real MP3 with cover, produced by the normal pipeline
    audio_file = await downloader._fetch_audio(f"{http_base}/clip.mp4")
    src = audio_file.path

    async def fake_download(self, file_id, destination=None, **kw):
        shutil.copy(src, destination)

    monkeypatch.setattr(Bot, "download", fake_download)
    audio_msg = Message(message_id=600, date=NOW, chat=CHAT,
                        audio=Audio(file_id="ORIG", file_unique_id="u-orig", duration=30,
                                    performer="Pop Smoke", title="Dior", file_size=500_000))
    await press("fx:slow", message=audio_msg)
    sent = session.of(SendAudio)[-1]
    assert sent.title == "Dior (slowed + reverb)" and "Slowed + reverb" in sent.caption
    # cached: a second press re-sends the same file_id instantly
    n = len(session.of(SendAudio))
    await press("fx:slow", message=audio_msg)
    assert len(session.of(SendAudio)) == n + 1 and isinstance(session.of(SendAudio)[-1].audio, str)
    await press("fx:up", message=audio_msg)
    assert session.of(SendAudio)[-1].title == "Dior (sped up)"


async def test_fx_filters_change_duration(media_dir, tmp_path):
    from bot.services import media
    src = tmp_path / "s.mp3"
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(media_dir / "clip.mp4"), "-vn", str(src)], check=True)
    up = await media.make_fx(src, tmp_path / "up.mp3", "up")
    slow = await media.make_fx(src, tmp_path / "slow.mp3", "slow")
    d_up = (await media.probe(up))["duration"]
    d_slow = (await media.probe(slow))["duration"]
    assert 22 < d_up < 26          # 30 s / 1.25 = 24 s
    assert 34 < d_slow < 37.5      # 30 s / 0.85 ≈ 35.3 s


async def test_admin_panel_owner_stats_broadcast(env, monkeypatch):
    session, db, send_text, press, _ = env
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import CopyMessage, EditMessageText as EMT
    from bot.config import config
    from bot.handlers import admin
    monkeypatch.setattr(config, "admin_ids", frozenset())
    monkeypatch.setattr(admin, "BROADCAST_DELAY", 0)

    # first /admin on a fresh bot makes you the owner
    await send_text("/admin")
    texts = [m.text for m in session.of(SendMessage)[-2:]]
    assert "владелец" in texts[0] and "Админ-панель" in texts[1]
    assert await db.admin_ids() == {USER.id}

    # other users: 2 normal + 1 that blocked the bot
    for uid in (1001, 1002, 1003):
        await db.ensure_user(uid, "uz")
    await press("adm:stats")
    stats = session.of(EMT)[-1].text
    assert "Всего пользователей: <b>4</b>" in stats and "🇺🇿 3" in stats

    calls = []
    orig = FakeSession._make

    async def make(self, bot, method):
        if isinstance(method, CopyMessage) and method.chat_id != CHAT.id:
            calls.append(method.chat_id)
            if method.chat_id == 1003:
                raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
            return Message(message_id=9, date=NOW, chat=Chat(id=method.chat_id, type="private"))
        if isinstance(method, CopyMessage):
            return Message(message_id=9, date=NOW, chat=CHAT)
        return await orig(self, bot, method)

    monkeypatch.setattr(FakeSession, "_make", make)
    await press("adm:bc")
    assert "Получателей: <b>4</b>" in session.of(EMT)[-1].text
    await send_text("🔥 Новый релиз уже в боте!")
    confirm = session.of(SendMessage)[-1]
    assert "Отправить" in confirm.reply_markup.inline_keyboard[0][0].text
    await press("adm:bc_go")
    import asyncio
    for _ in range(50):
        await asyncio.sleep(0.02)
        if "завершена" in session.of(EMT)[-1].text:
            break
    report = session.of(EMT)[-1].text
    assert sorted(calls) == [1001, 1002, 1003]
    assert "Доставлено: <b>3</b>" in report and "Заблокировали бота: <b>1</b>" in report
    assert 1003 not in await db.broadcast_ids()


async def test_admin_ignores_strangers(env, monkeypatch):
    session, db, send_text, press, _ = env
    from bot.config import config
    monkeypatch.setattr(config, "admin_ids", frozenset({777}))
    await send_text("/admin")
    await send_text("/stats")
    assert not session.of(SendMessage)  # strangers get no answer at all
    await press("adm:stats")
    assert session.of(AnswerCallbackQuery)[-1].text == "⛔️"


async def test_english_language(env):
    session, db, send_text, press, _ = env
    await press("l:en")
    sent = session.of(SendMessage)[-1]
    assert sent.text == "✅ Language: English"
    assert sent.reply_markup.keyboard[0][0].text == "🔥 Top of the week"
    await send_text("❓ Help")
    assert "How it works" in session.of(SendMessage)[-1].text


async def test_shazam_always_tries_other_sources(env, monkeypatch, http_base, media_dir, data_dir):
    """The screenshot bug: Shazam found the song but the first YouTube video failed -> no MP3."""
    session, _, _, _, send_media = env

    async def fake_fetch(bot, file_id, size):
        d = data_dir / "in3"
        d.mkdir(exist_ok=True)
        shutil.copy(media_dir / "clip.mp4", d / "input")
        return d / "input"

    searches, downloads = [], []

    async def fake_search(q, limit=30):
        searches.append(q)
        return [
            downloader.Track(id="geolock", title="UzBoom - Kecholmadim (Official Video)"),
            downloader.Track(id="other", title="Kecholmadim - UzBoom (audio)"),
            downloader.Track(id="unrelated", title="Some other song"),
        ]

    real = downloader.download_audio

    async def fake_download(video_id, url=None):
        downloads.append(video_id)
        if video_id == "geolock":
            raise downloader.DownloadFailed("Video unavailable. This video is not available in your country")
        return await real(video_id, url=f"{http_base}/clip.mp4")

    monkeypatch.setattr(rec_handler, "_fetch", fake_fetch)
    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(recognizer.Song("Kecholmadim", "UzBoom")))
    monkeypatch.setattr(downloader, "search", fake_search)
    monkeypatch.setattr(downloader, "download_audio", fake_download)
    await send_media(voice=__import__("aiogram").types.Voice(file_id="v", file_unique_id="u", duration=10))
    assert downloads == ["geolock", "other"]  # unrelated result is never tried
    assert session.of(SendAudio), "MP3 must be sent"
    card = session.of(SendMessage)[-1]
    assert card.reply_markup is None  # no "Open in Shazam" button
    assert not any("не удалось" in (m.text or "") for m in session.of(SendMessage))


async def test_youtube_blocked_mp3_comes_from_catalogue_site(env, monkeypatch, media_dir, data_dir):
    """Live bug: YouTube says "Sign in to confirm you're not a bot" on every route ->
    the MP3 must come from an MP3 catalogue site, without hammering YouTube."""
    from bot.services import mp3sites

    session, _, _, _, send_media = env
    mp3 = media_dir / "song.mp3"
    if not mp3.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=40",
                        "-b:a", "128k", str(mp3)], check=True)

    async def fake_fetch(bot, file_id, size):
        d = data_dir / "in4"
        d.mkdir(exist_ok=True)
        shutil.copy(media_dir / "clip.mp4", d / "input")
        return d / "input"

    yt_downloads, site_queries = [], []

    async def blocked_download(video_id, url=None):
        yt_downloads.append(video_id)
        monkeypatch.setattr(downloader, "_yt_blocked_until", time.time() + 900)
        raise downloader.DownloadFailed("Sign in to confirm you're not a bot")

    async def fake_search(q, limit=30):
        return [downloader.Track(id="a", title="UzBoom - Kecholmadim")]

    def site_search(q):
        site_queries.append(q)
        return [mp3sites.SiteTrack("Other", "Boshqa qo'shiq", "http://x/1.mp3"),
                mp3sites.SiteTrack("UzBoom", "Kecholmadim", "http://x/2.mp3")], "http://x"

    def site_download(tr, referer, workdir):
        assert tr.url == "http://x/2.mp3"
        shutil.copy(mp3, workdir / "song.mp3")
        return workdir / "song.mp3", None

    monkeypatch.setattr(rec_handler, "_fetch", fake_fetch)
    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(recognizer.Song("Kecholmadim", "UzBoom")))
    monkeypatch.setattr(downloader, "search", fake_search)
    monkeypatch.setattr(downloader, "download_audio", blocked_download)
    monkeypatch.setattr(mp3sites, "search_sync", site_search)
    monkeypatch.setattr(mp3sites, "download_sync", site_download)
    await send_media(voice=__import__("aiogram").types.Voice(file_id="v", file_unique_id="u", duration=10))
    audio = session.of(SendAudio)
    assert audio, "MP3 must be sent"
    assert audio[-1].performer == "UzBoom" and audio[-1].title == "Kecholmadim"
    assert len(yt_downloads) <= 1  # YouTube is not retried 5 times once it is known to be blocked
    assert not any("не удалось" in (m.text or "") for m in session.of(SendMessage))


def _choice_buttons(session) -> list[str]:
    return [b.callback_data for row in session.of(SendMessage)[-1].reply_markup.inline_keyboard for b in row]


async def test_link_audio_and_shazam_choices(env, monkeypatch, http_base):
    """🎵 Audio MP3 and 🔍 Find the music under a pasted link."""
    session, _, send_text, press, _ = env
    real = downloader._fetch_audio
    fetched = []

    async def fake_fetch_audio(target, soundcloud=False):
        fetched.append(target)
        return await real(f"{http_base}/clip.mp4")

    monkeypatch.setattr(downloader, "_fetch_audio", fake_fetch_audio)
    await send_text("https://www.instagram.com/reel/ABC123/")
    video_btn, audio_btn, shazam_btn = _choice_buttons(session)

    await press(audio_btn)
    audio = session.of(SendAudio)[-1]
    assert not isinstance(audio.audio, str)  # uploaded mp3
    assert fetched == ["https://www.instagram.com/reel/ABC123/"]

    await press(audio_btn)  # second time: cached file_id
    assert isinstance(session.of(SendAudio)[-1].audio, str) and len(fetched) == 1

    async def fake_search(q, limit=30):
        return [downloader.Track(id="oorVWW9ywG0", title="POP SMOKE - DIOR")]

    async def fake_rec(path):
        assert Path(path).exists()
        return recognizer.Song("Dior", "Pop Smoke")

    monkeypatch.setattr(recognizer, "recognize", fake_rec)
    monkeypatch.setattr(downloader, "search", fake_search)
    await press(shazam_btn)
    assert any("Shazam нашёл" in (m.text or "") for m in session.of(SendMessage))
    assert "Найдено по звуку" in session.of(SendAudio)[-1].caption

    await press("dl:v:doesnotexist")
    from aiogram.methods import AnswerCallbackQuery as ACQ
    assert "устарела" in session.of(ACQ)[-1].text


async def test_youtube_link_blocked_uses_invidious(env, monkeypatch, media_dir):
    """Live bug: every YouTube link failed with "Sign in to confirm you're not a bot"."""
    from bot.services import ytalt

    session, _, send_text, press, _ = env

    def blocked(url, opts, download=True):
        raise downloader.yt_dlp.utils.DownloadError("ERROR: [youtube] Uk9u4ikJY0U: Sign in to confirm you're not a bot")

    alt_calls = []

    def fake_alt(video_id, workdir, height, limit):
        alt_calls.append(video_id)
        shutil.copy(media_dir / "clip.mp4", workdir / f"{video_id}.mp4")
        return ytalt.Info(id=video_id, title="Superliga 20-tur", author="Futbol", duration=30, thumb="")

    monkeypatch.setattr(downloader, "_extract", blocked)
    monkeypatch.setattr(ytalt, "download_video", fake_alt)
    await send_text("https://youtu.be/Uk9u4ikJY0U?si=fHmqBifIGrlqgnXW")
    await press(_choice_buttons(session)[0])
    assert alt_calls == ["Uk9u4ikJY0U"]
    assert session.of(SendVideo), "video must be sent"
    assert not any("Не получилось" in (m.text or "") for m in session.of(SendMessage))


async def test_admin_uploads_youtube_cookies(env, monkeypatch, data_dir):
    session, db, _, _, send_media = env
    from aiogram.types import Document
    from bot.config import config
    from bot.handlers import admin

    monkeypatch.setattr(config, "admin_ids", frozenset({USER.id}))
    monkeypatch.setattr(config, "cookies_file", "")
    payload = {"data": b"# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n"}

    async def fake_download(self, file_id, destination=None, **kw):
        Path(destination).write_bytes(payload["data"])

    checked = []

    async def fake_check(url, use_proxy):
        checked.append(config.cookies)
        return None

    monkeypatch.setattr(Bot, "download", fake_download)
    monkeypatch.setattr(downloader, "check_route_async", fake_check)
    monkeypatch.setattr(downloader, "_yt_blocked_until", time.time() + 900)
    await send_media(document=Document(file_id="f", file_unique_id="u", file_name="cookies.txt", file_size=100))
    assert config.cookies == str(data_dir / "cookies.txt")
    assert checked == [config.cookies]  # checked right away, with the new cookies
    assert not downloader.youtube_blocked()
    assert "YouTube работает" in session.of(EditMessageText)[-1].text

    payload["data"] = b"hello"
    await send_media(document=Document(file_id="f2", file_unique_id="u2", file_name="notes.txt", file_size=5))
    assert "не похоже" in session.of(SendMessage)[-1].text
    assert (data_dir / "cookies.txt").read_bytes().startswith(b"# Netscape")  # old cookies kept


async def test_tiktok_falls_back_to_tikwm(env, monkeypatch, media_dir):
    from bot.services import tiktok

    session, _, send_text, press, _ = env

    def no_formats(url, opts, download=True):
        raise downloader.yt_dlp.utils.DownloadError("ERROR: [TikTok] 7312: No video formats found!")

    def fake_get(url, referer="", timeout=20):
        if url.startswith(tiktok.API):
            return json.dumps({"code": 0, "data": {
                "id": "7312", "title": "dance", "duration": 30, "author": {"nickname": "kid"},
                "play": "/video/media/play/7312.mp4", "hdplay": "/video/media/hdplay/7312.mp4",
                "music_info": {"title": "Dior", "author": "Pop Smoke"}}}).encode()
        assert url == "https://www.tikwm.com/video/media/hdplay/7312.mp4"  # HD, absolute URL
        return (media_dir / "clip.mp4").read_bytes()

    monkeypatch.setattr(downloader, "_extract", no_formats)
    monkeypatch.setattr(tiktok, "http_get", fake_get)
    await send_text("https://vt.tiktok.com/ZSabc/")
    await press(_choice_buttons(session)[0])
    assert session.of(SendVideo), "video must be sent"
    await send_text("https://vt.tiktok.com/ZSxyz/")
    await press(_choice_buttons(session)[1])
    audio = session.of(SendAudio)[-1]
    assert (audio.performer, audio.title) == ("Pop Smoke", "Dior")


async def test_youtube_blocked_video_and_audio_via_cobalt(env, monkeypatch, media_dir):
    """The user won't set up cookies: blocked YouTube must work through cobalt with zero setup."""
    from bot.services import cobalt

    session, _, send_text, press, _ = env

    def blocked(url, opts, download=True):
        raise downloader.yt_dlp.utils.DownloadError("ERROR: [youtube] Uk9u4ikJY0U: Sign in to confirm you're not a bot")

    mp3 = media_dir / "cobalt.mp3"
    if not mp3.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=500:duration=20",
                        "-b:a", "128k", str(mp3)], check=True)
    asked = []

    def fake_fetch(url, audio, max_height=1080):
        asked.append(("audio" if audio else "video", url))
        if audio:
            return [(mp3.read_bytes(), "UzBoom - Kecholmadim (320kbps).mp3")]
        return [((media_dir / "clip.mp4").read_bytes(), "video.mp4")]

    monkeypatch.setattr(downloader, "_extract", blocked)
    monkeypatch.setattr(cobalt, "fetch", fake_fetch)
    await send_text("https://youtu.be/Uk9u4ikJY0U?si=abc")
    video_btn, audio_btn, _ = _choice_buttons(session)
    await press(video_btn)
    assert session.of(SendVideo), "video must be sent"
    await press(audio_btn)
    audio = session.of(SendAudio)[-1]
    assert (audio.performer, audio.title) == ("UzBoom", "Kecholmadim")
    assert [k for k, _ in asked] == ["video", "audio"]
    assert not any("Не получилось" in (m.text or "") for m in session.of(SendMessage))


async def test_sent_mp3_goes_to_library_and_is_found(env, monkeypatch):
    """Someone sends an MP3 -> it is saved; anyone searching that song gets that exact file."""
    session, db, send_text, press, send_media = env
    await send_media(audio=Audio(file_id="USERMP3", file_unique_id="um1", duration=200,
                                 performer="UzBoom", title="Kecholmadim"))
    assert "добавлен в базу" in session.of(SendMessage)[-1].text

    async def no_youtube(q, limit=30):
        return []

    monkeypatch.setattr(downloader, "search", no_youtube)
    await send_text("kecholmadim")
    edit = session.of(EditMessageText)[-1]
    assert "UzBoom - Kecholmadim" in edit.text
    sid = edit.reply_markup.inline_keyboard[0][0].callback_data.split(":")[1]
    await press(f"t:{sid}:0")
    assert session.of(SendAudio)[-1].audio == "USERMP3"

    # Shazam finds the same song -> the library file is sent, nothing is downloaded
    async def must_not_download(*a, **k):
        raise AssertionError("should come from the library")

    monkeypatch.setattr(downloader, "download_song", must_not_download)
    from bot.common import send_song
    n = len(session.of(SendAudio))
    await send_song(session.bot, db, 42, "Kecholmadim", "UzBoom", "ru")
    assert session.of(SendAudio)[-1].audio == "USERMP3" and len(session.of(SendAudio)) == n + 1


async def test_lyrics_button(env, monkeypatch):
    from bot.services import lyrics

    session, _, _, press, _ = env
    asked = []

    def fake_find(title, artist):
        asked.append((title, artist))
        return "Ko'zlaring\nKecholmadim <3" if title == "Kecholmadim" else None

    monkeypatch.setattr(lyrics, "find", fake_find)
    msg = Message(message_id=600, date=NOW, chat=CHAT,
                  audio=Audio(file_id="A", file_unique_id="a", duration=1, performer="UzBoom", title="Kecholmadim"))
    await press("ly", message=msg)
    text = session.of(SendMessage)[-1].text
    assert "📝 <b>UzBoom - Kecholmadim</b>" in text and "Kecholmadim &lt;3" in text
    await press("ly", message=msg)  # cached: no second lookup
    assert asked == [("Kecholmadim", "UzBoom")]
    other = Message(message_id=601, date=NOW, chat=CHAT,
                    audio=Audio(file_id="B", file_unique_id="b", duration=1, performer="X", title="Nothing"))
    await press("ly", message=other)
    assert "не нашёл" in session.of(SendMessage)[-1].text


async def test_inline_mode(env, monkeypatch, fake_audio):
    from aiogram.methods import AnswerInlineQuery, EditMessageMedia
    from aiogram.types import InlineQuery

    session, db, send_text, press, _ = env
    await db.add_to_library("lib1", "LIBFILE", "Dior", "Pop Smoke", 173)

    async def fake_search(q, limit=30):
        return [downloader.Track(id="oorVWW9ywG0", title="POP SMOKE - DIOR (OFFICIAL VIDEO)", duration=173)]

    monkeypatch.setattr(downloader, "search", fake_search)
    bot, dp = session.bot, session.dp
    q = InlineQuery(id="iq1", from_user=USER, query="pop smoke dior", offset="").as_(bot)
    await dp.feed_update(bot, Update(update_id=9001, inline_query=q).as_(bot))
    answer = session.of(AnswerInlineQuery)[-1]
    kinds = [r.type for r in answer.results]
    assert kinds == ["audio", "article"]
    assert answer.results[0].audio_file_id == "LIBFILE"
    article = answer.results[1]
    assert article.id == "y:oorVWW9ywG0" and "POP SMOKE - DIOR" in article.title

    cq = CallbackQuery(id="c1", from_user=USER, chat_instance="c", data="il:oorVWW9ywG0",
                       inline_message_id="INL1").as_(bot)
    await dp.feed_update(bot, Update(update_id=9002, callback_query=cq).as_(bot))
    edit = session.of(EditMessageMedia)[-1]
    assert edit.inline_message_id == "INL1" and edit.media.media.startswith("AUD")
    assert fake_audio == ["oorVWW9ywG0"]
    assert session.of(DeleteMessage), "the helper upload in the user's chat is removed"


async def test_group_link_downloads_without_menu(env, monkeypatch, http_base):
    session, _, _, _, _ = env
    real_dl = downloader.download_video

    async def fake_video(url, platform):
        return await real_dl(f"{http_base}/clip.mp4", platform)

    monkeypatch.setattr(downloader, "download_video", fake_video)
    bot, dp = session.bot, session.dp
    group = Chat(id=-100500, type="supergroup", title="Friends")
    msg = Message(message_id=77, date=NOW, chat=group, from_user=USER, text="look https://vt.tiktok.com/ZSq/").as_(bot)
    await dp.feed_update(bot, Update(update_id=9100, message=msg).as_(bot))
    assert session.of(SendVideo), "video sent straight away in groups"
    assert not any(m.reply_markup and "dl:v:" in str(m.reply_markup) for m in session.of(SendMessage))


# ---------------------------------------------------------------- ringtone, video note, mood, wrapped

@pytest.fixture
def stereo_mp3(tmp_path) -> Path:
    out = tmp_path / "stereo.mp3"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=45",
        "-f", "lavfi", "-i", "sine=frequency=660:duration=45",
        "-filter_complex", "[0][1]amerge=inputs=2,pan=stereo|c0=c0+0.5*c1|c1=c0+0.2*c1",
        "-c:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
    return out


def _fake_download(monkeypatch, src: Path):
    async def fake(self, file, destination=None, **kw):
        shutil.copy(src, destination)
        return destination

    monkeypatch.setattr(Bot, "download", fake)


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,channels:"
                          "format=duration,format_name", "-of", "json", str(path)], capture_output=True, check=True)
    return json.loads(out.stdout)


async def test_media_minus_ringtone_note_voice(tmp_path, stereo_mp3, media_dir):
    from bot.services import media
    assert await media.make_minus(stereo_mp3, tmp_path / "minus.mp3")
    assert await media.make_minus(media_dir / "clip.mp4", tmp_path / "mono.mp3") is None  # mono: nothing to cancel
    for mode in ("8d", "bass"):
        assert await media.make_fx(stereo_mp3, tmp_path / f"{mode}.mp3", mode)

    m4r, mp3 = await media.make_ringtone(stereo_mp3, tmp_path, "Artist - Song")
    assert m4r.suffix == ".m4r" and mp3.suffix == ".mp3"
    info = _probe(m4r)
    assert info["streams"][0]["codec_name"] == "aac" and 29 <= float(info["format"]["duration"]) <= 31

    note = await media.to_video_note(media_dir / "clip.mp4", tmp_path / "note.mp4")
    v = [s for s in _probe(note)["streams"] if s.get("width")][0]
    assert v["width"] == v["height"] == 512
    voice = await media.to_voice(media_dir / "clip.mp4", tmp_path / "voice.ogg")
    assert _probe(voice)["streams"][0]["codec_name"] == "opus"


async def test_ringtone_button(env, monkeypatch, stereo_mp3):
    from aiogram.methods import SendDocument
    session, _, _, press, _ = env
    _fake_download(monkeypatch, stereo_mp3)
    msg = Message(message_id=5, date=NOW, chat=CHAT,
                  audio=Audio(file_id="A", file_unique_id="ua", duration=45, title="Dior", performer="Pop Smoke"))
    await press("rt", message=msg)
    docs = session.of(SendDocument)
    assert [d.document.filename for d in docs] == ["Pop Smoke - Dior.m4r", "Pop Smoke - Dior.mp3"]
    assert "Рингтон" in docs[-1].caption


async def test_video_note_and_voice(env, monkeypatch, media_dir):
    from aiogram.methods import SendVideoNote, SendVoice
    session, db, _, press, _ = env
    _fake_download(monkeypatch, media_dir / "clip.mp4")
    video = Video(file_id="V", file_unique_id="uv", width=720, height=1280, duration=30, file_size=100_000)
    await press("vn:note", message=Message(message_id=6, date=NOW, chat=CHAT, video=video))
    assert len(session.of(SendVideoNote)) == 1
    await db.put_file("uv:tok", "video", "V", {"size": 100_000})
    await press("vn:voice:tok")
    assert len(session.of(SendVoice)) == 1
    await press("vn:voice:gone")
    assert session.of(AnswerCallbackQuery)[-1].show_alert


async def test_mood_playlist(env, monkeypatch):
    session, db, send_text, press, _ = env
    queries = []

    async def fake_search(q, limit=30):
        queries.append(q)
        return [downloader.Track(id=f"{len(queries)}x{i:08d}", title=f"{q} {i}", duration=200) for i in range(3)]

    monkeypatch.setattr(downloader, "search", fake_search)
    await send_text("🎧 Настроение")
    kb = session.of(SendMessage)[-1].reply_markup.inline_keyboard
    assert kb[0][0].callback_data == "mood:sad"
    await press("mood:sad")
    assert len(queries) == 2 and all(str(NOW.year) in q for q in queries)
    text = session.of(EditMessageText)[-1].text
    assert "Грустное" in text and "1." in text


async def test_wrapped_card(env, tmp_path):
    session, db, send_text, _, _ = env
    await send_text(f"📊 Мой {NOW.year}")
    assert "мало данных" in session.of(SendMessage)[-1].text
    for title, artist in [("Dior", "Pop Smoke"), ("Dior", "Pop Smoke"), ("Welcome", "Pop Smoke"), ("Yor", "Shahzoda")]:
        await db.log_play(USER.id, title, artist)
    stats = await db.year_stats(USER.id, NOW.year)
    assert stats["total"] == 4 and stats["days"] == 1
    assert stats["artists"][0] == ("Pop Smoke", 3) and stats["songs"][0][:2] == ("Dior", "Pop Smoke")
    await send_text("/wrapped")
    photo = session.of(SendPhoto)[-1]
    assert f"{NOW.year}" in photo.caption and photo.photo.filename.endswith(".png")

    from PIL import Image
    from bot.services import wrapped
    out = wrapped.render(stats, {"title": "Твой 2026", "tracks": "треков", "days": "дней", "artists": "Артисты",
                                 "songs": "Песни"}, "TestMusicBot", tmp_path / "w.png")
    assert Image.open(out).size == (1080, 1350)


async def test_ringtone_picks_the_loud_part(tmp_path):
    from bot.services import media
    src = tmp_path / "quiet_loud.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=70",
                    "-af", "volume='if(lt(t,35),0.05,1)':eval=frame", "-c:a", "libmp3lame", str(src)], check=True)
    start = await media.best_part(src)
    assert 15 <= start <= 40
