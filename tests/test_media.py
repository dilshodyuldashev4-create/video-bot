"""Real ffmpeg + yt-dlp pipelines against a local HTTP server (no internet needed)."""
from bot.services import downloader, media, recognizer


async def test_probe_and_thumb(media_dir, tmp_path):
    info = await media.probe(media_dir / "clip.mp4")
    assert (info["width"], info["height"]) == (720, 1280)
    assert 29 < info["duration"] < 31 and info["has_audio"]
    thumb = await media.make_thumb(media_dir / "clip.mp4", tmp_path / "t.jpg")
    tinfo = await media.probe(thumb)
    assert max(tinfo["width"], tinfo["height"]) == 320


async def test_extract_audio_and_wav(media_dir, tmp_path):
    ogg = await media.extract_audio(media_dir / "clip.mp4", tmp_path / "a.ogg")
    assert ogg and ogg.stat().st_size < 600_000
    wav = await media.to_wav(media_dir / "clip.mp4", tmp_path / "s.wav", 10, recognizer.SEGMENT)
    info = await media.probe(wav)
    assert abs(info["duration"] - recognizer.SEGMENT) < 0.2


async def test_video_download_pipeline(http_base):
    res = await downloader.download_video(f"{http_base}/clip.mp4", "tiktok")
    assert len(res.files) == 1 and res.files[0].suffix == ".mp4"
    info = await media.probe(res.files[0])
    assert info["height"] == 1280 and info["has_audio"]


async def test_audio_download_pipeline(http_base):
    audio = await downloader.download_audio("x", url=f"{http_base}/clip.mp4")
    assert audio.path.suffix == ".mp3"
    info = await media.probe(audio.path)
    assert info["has_audio"] and 29 < info["duration"] < 31


async def test_recognize_calls_shazam_on_segments(media_dir, monkeypatch):
    seen = []

    async def fake(path):
        seen.append(path)
        return recognizer.Song("Dior", "Pop Smoke") if len(seen) == 2 else None

    monkeypatch.setattr(recognizer, "_recognize_file", fake)
    song = await recognizer.recognize(media_dir / "clip.mp4")
    assert song.query == "Pop Smoke - Dior" and len(seen) == 2


async def test_recognize_no_audio(media_dir):
    assert await recognizer.recognize(media_dir / "silent.mp4") is None


def test_parse_shazam_payload():
    payload = {"track": {"title": "Dior", "subtitle": "Pop Smoke",
                         "images": {"coverart": "c.jpg"}, "url": "https://shazam/x"}}
    s = recognizer._parse(payload)
    assert (s.title, s.artist, s.cover) == ("Dior", "Pop Smoke", "c.jpg")
    assert recognizer._parse({"matches": []}) is None
