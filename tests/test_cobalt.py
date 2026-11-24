"""YouTube through public cobalt instances."""
import json

import pytest

from bot.services import cobalt


def test_parse_list_keeps_open_youtube_instances():
    data = [
        {"api": "cobalt.good.example", "online": True, "score": 90, "services": {"youtube": True}},
        {"api": "https://best.example/", "online": True, "score": 100, "services": {"youtube": True}},
        {"api": "auth.example", "online": True, "score": 99, "info": {"auth": True}, "services": {"youtube": True}},
        {"api": "noyt.example", "online": True, "score": 95, "services": {"youtube": False}},
        {"api": "down.example", "online": False, "score": 98},
    ]
    assert cobalt.parse_list(data) == ["https://best.example", "https://cobalt.good.example"]


def test_fetch_tries_instances_until_one_works(monkeypatch):
    monkeypatch.setattr(cobalt, "instances", lambda: ["https://bad.example", "https://ok.example"])
    monkeypatch.setattr(cobalt, "_good", [])
    sent = []

    def fake_get(url, referer="", timeout=20, data=None, headers=None):
        if data:
            sent.append((url, json.loads(data)))
            if url.startswith("https://bad.example"):
                return json.dumps({"status": "error", "error": {"code": "error.api.youtube.login"}}).encode()
            return json.dumps({"status": "tunnel", "url": "https://ok.example/tunnel?id=1",
                               "filename": "Kecholmadim - UzBoom.mp3"}).encode()
        assert url == "https://ok.example/tunnel?id=1"
        return b"\xff\xfb" + b"0" * 50_000

    monkeypatch.setattr(cobalt, "http_get", fake_get)
    files = cobalt.fetch("https://youtu.be/Uk9u4ikJY0U", audio=True)
    assert files[0][1] == "Kecholmadim - UzBoom.mp3" and len(files[0][0]) > 50_000
    assert [u for u, _ in sent] == ["https://bad.example/", "https://ok.example/"]
    assert sent[0][1]["downloadMode"] == "audio" and sent[0][1]["audioFormat"] == "mp3"
    assert cobalt._good == ["https://ok.example"]


def test_all_instances_fail_pauses(monkeypatch):
    monkeypatch.setattr(cobalt, "instances", lambda: ["https://bad.example"])

    def fake_get(url, **kw):
        raise OSError("refused")

    monkeypatch.setattr(cobalt, "http_get", fake_get)
    with pytest.raises(RuntimeError):
        cobalt.fetch("https://youtu.be/x", audio=False)
    assert not cobalt.available()
