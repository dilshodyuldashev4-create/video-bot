"""YouTube via Invidious / Piped when the server IP is blocked."""
import json
import subprocess

import pytest

from bot.services import ytalt


@pytest.fixture
def split_media(media_dir):
    v, a = media_dir / "v.mp4", media_dir / "a.m4a"
    if not v.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(media_dir / "clip.mp4"), "-an", "-c", "copy", "-movflags", "+faststart", str(v)],
                       check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(media_dir / "clip.mp4"), "-vn", "-c", "copy", "-movflags", "+faststart", str(a)],
                       check=True)
    return v, a


def _fake_api(monkeypatch, responses: dict, fail: set = frozenset()):
    calls = []

    def fake_get(url, referer="", timeout=20):
        calls.append(url)
        for prefix, body in responses.items():
            if url.startswith(prefix):
                if prefix in fail:
                    raise OSError("connection refused")
                return json.dumps(body).encode() if not isinstance(body, bytes) else body
        raise OSError(f"unexpected {url}")

    monkeypatch.setattr(ytalt, "http_get", fake_get)
    monkeypatch.setattr(ytalt, "_good", [])
    return calls


def test_invidious_video_merge_and_audio(monkeypatch, http_base, split_media, tmp_path):
    monkeypatch.setattr(ytalt, "instances", lambda: [("invidious", "https://dead.example"),
                                                       ("invidious", http_base)])
    inv = {
        "title": "Superliga 20-tur", "author": "Futbol TV", "lengthSeconds": 30,
        "videoThumbnails": [{"url": "/vi/x/maxres.jpg"}],
        "adaptiveFormats": [
            {"url": "/v.mp4", "type": 'video/mp4; codecs="avc1.64001F"', "resolution": "720p", "bitrate": "1500000",
             "clen": "100000"},
            {"url": "/huge.mp4", "type": 'video/mp4; codecs="avc1.640028"', "resolution": "1080p",
             "clen": str(500 * 1024 * 1024)},
            {"url": "/a.m4a", "type": 'audio/mp4; codecs="mp4a.40.2"', "bitrate": "130000", "clen": "50000"},
            {"url": "/a.webm", "type": 'audio/webm; codecs="opus"', "bitrate": "60000"},
        ],
        "formatStreams": [{"url": "/clip.mp4", "type": "video/mp4", "resolution": "360p"}],
    }
    calls = _fake_api(monkeypatch, {"https://dead.example": {}, f"{http_base}/api/v1/videos/": inv,
                                    f"{http_base}/vi/": b"x" * 2000}, fail={"https://dead.example"})
    info = ytalt.download_video("Uk9u4ikJY0U", tmp_path, 1080, 49 * 1024 * 1024)
    assert info.title == "Superliga 20-tur" and info.source == http_base
    out = tmp_path / "Uk9u4ikJY0U.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(out)],
                                      capture_output=True, check=True).stdout)
    kinds = sorted(s["codec_type"] for s in probe["streams"])
    assert kinds == ["audio", "video"]  # 720p video-only merged with the m4a audio; 1080p skipped (too big)
    assert any("?local=true" in c for c in calls)
    assert ytalt._good[0] == ("invidious", http_base)  # working instance remembered

    info, mp3, cover = ytalt.download_audio("Uk9u4ikJY0U", tmp_path)
    assert mp3.exists() and mp3.stat().st_size > 10_000 and cover is not None


def test_piped_and_all_down_pause(monkeypatch, http_base, split_media, tmp_path):
    monkeypatch.setattr(ytalt, "instances", lambda: [("piped", http_base)])
    piped = {"title": "Song", "uploader": "Artist", "duration": 30, "thumbnailUrl": "",
             "videoStreams": [{"url": f"{http_base}/v.mp4", "mimeType": "video/mp4", "quality": "360p",
                               "videoOnly": False, "codec": "avc1.4d401e"}],
             "audioStreams": []}
    _fake_api(monkeypatch, {f"{http_base}/streams/": piped})
    ytalt.download_video("abcdefghijk", tmp_path, 720, 49 * 1024 * 1024)
    assert (tmp_path / "abcdefghijk.mp4").stat().st_size > 10_000  # muxed stream when there is no separate audio

    monkeypatch.setattr(ytalt, "instances", lambda: [("invidious", "https://a.example"), ("piped", "https://b.example")])
    _fake_api(monkeypatch, {"https://a.example": {}, "https://b.example": {}}, fail={"https://a.example", "https://b.example"})
    with pytest.raises(RuntimeError):
        ytalt.fetch_info("abcdefghijk")
    assert not ytalt.available()  # paused: next songs don't wait for dead instances


def test_empty_ffmpeg_output_is_a_failure(monkeypatch, tmp_path):
    """ffmpeg exits 0 with an empty file when the stream server hangs up: that's not a video."""
    monkeypatch.setattr(ytalt, "fetch_info", lambda vid: ytalt.Info(
        id=vid, title="t", author="a", duration=1, thumb="", source="x",
        streams=[ytalt.Stream(url="http://x/v", mime="video/mp4", height=360)]))
    monkeypatch.setattr(ytalt, "_ffmpeg", lambda args, timeout=900: open(args[-1], "wb").write(b"0" * 262))
    with pytest.raises(RuntimeError):
        ytalt.download_video("abcdefghijk", tmp_path, 720, 49 * 1024 * 1024)
