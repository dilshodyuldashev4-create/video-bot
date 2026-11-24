"""End-to-end handler flows with a fake Telegram API (no network)."""
import datetime
import shutil
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
    from bot.handlers import library, links, recognize, search, start
    for r in (library.router, links.router, recognize.router, search.router, start.router):
        r._parent_router = None  # allow a fresh Dispatcher per test
    dp = build_dispatcher(db)
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
    assert [b.callback_data for b in kb[1]] == ["fx:up", "fx:slow"]
    assert kb[2][1].url == "https://t.me/TestMusicBot?startgroup=true"
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
    video = session.of(SendVideo)[-1]
    assert (video.width, video.height, video.supports_streaming) == (720, 1280, True)
    assert video.thumbnail is not None
    btn = video.reply_markup.inline_keyboard[0][0]
    assert btn.callback_data.startswith("g:")

    # same link again -> cached file_id, no second download
    n_before = len(session.of(SendVideo))
    monkeypatch.setattr(downloader, "download_video", None)
    await send_text("https://vm.tiktok.com/ZMabc123/?lang=ru")
    assert len(session.of(SendVideo)) == n_before + 1
    assert isinstance(session.of(SendVideo)[-1].video, str)  # file_id, not a re-upload

    async def fake_rec(path):
        assert Path(path).exists()
        return recognizer.Song("Dior", "Pop Smoke")

    async def fake_best(title, artist):
        return downloader.Track(id="oorVWW9ywG0", title="POP SMOKE - DIOR (OFFICIAL VIDEO)")

    monkeypatch.setattr(recognizer, "recognize", fake_rec)
    monkeypatch.setattr(downloader, "find_best", fake_best)
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
    assert "Не смог узнать" in session.of(SendMessage)[-1].text

    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(recognizer.Song("Dior", "Pop Smoke")))
    monkeypatch.setattr(downloader, "find_best", lambda t, a: _async(downloader.Track(id="abc", title="Dior")))
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
    assert sent.reply_markup.keyboard[1][0].text == "❤️ Mening musiqam"
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
    assert "t.me/share/url" in kb.inline_keyboard[2][0].url

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
    monkeypatch.setattr(downloader, "find_best", lambda t, a: _async(downloader.Track(id="cov", title="Dior")))
    await send_media(video=Video(file_id="x", file_unique_id="u", width=1, height=1, duration=30))
    photo = session.of(SendPhoto)[-1]
    assert photo.photo == "https://is1.example/cover.jpg" and "Shazam нашёл" in photo.caption
    assert photo.reply_markup.inline_keyboard[0][0].url == "https://www.shazam.com/track/1"
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

    async def fake_best(title, artist):
        found.append((artist, title))
        return downloader.Track(id="uzhit", title=f"{artist} - {title}")

    monkeypatch.setattr(downloader, "find_best", fake_best)
    await send_text("🇺🇿 Топ UZ")
    edit = session.of(EditMessageText)[-1]
    assert "Топ Узбекистана" in edit.text and "<b>2.</b> Pop Smoke - Dior" in edit.text
    sid = edit.reply_markup.inline_keyboard[0][0].callback_data.split(":")[1]
    await press(f"t:{sid}:1")
    assert found == [("Pop Smoke", "Dior")] and fake_audio == ["uzhit"]
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
