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
    from bot.handlers import links, recognize, search, start
    for r in (links.router, recognize.router, search.router, start.router):
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
    assert "1. POP SMOKE - DIOR 0" in edit.text and "10. POP SMOKE - DIOR 9" in edit.text
    rows = edit.reply_markup.inline_keyboard
    assert len(rows[0]) == 5 and len(rows[1]) == 5

    await press("p:1:1")
    assert "1. POP SMOKE - DIOR 10" in session.of(EditMessageText)[-1].text

    await press("t:1:3")
    audio = session.of(SendAudio)[-1]
    assert fake_audio == ["id000000003"]
    assert audio.caption.startswith("🎧") and "@TestMusicBot" in audio.caption
    assert audio.reply_markup.inline_keyboard[0][0].url == "https://t.me/TestMusicBot?startgroup=true"

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
    assert "Ничего не нашёл" in session.of(EditMessageText)[-1].text


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
    assert "Dior" in audio.caption and "Pop Smoke" in audio.caption
    assert fake_audio == ["oorVWW9ywG0"]


async def test_unsupported_link(env):
    session, _, send_text, _, _ = env
    await send_text("https://example.com/x")
    assert "не поддерживаю" in session.of(SendMessage)[-1].text


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
    assert "Не удалось распознать" in session.of(SendMessage)[-1].text

    monkeypatch.setattr(recognizer, "recognize", lambda p: _async(recognizer.Song("Dior", "Pop Smoke")))
    monkeypatch.setattr(downloader, "find_best", lambda t, a: _async(downloader.Track(id="abc", title="Dior")))
    from aiogram.types import Voice
    await send_media(voice=Voice(file_id="v", file_unique_id="u", duration=10))
    assert session.of(SendAudio) and "Pop Smoke" in session.of(SendAudio)[-1].caption


async def test_language_switch(env):
    session, db, send_text, press, _ = env
    await press("l:uz")
    assert "O'zbekcha" in session.of(EditMessageText)[-1].text
    await send_text("/start")
    assert "Salom" in session.of(SendMessage)[-1].text


async def _async(v):
    return v
