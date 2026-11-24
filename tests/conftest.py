import functools
import http.server
import os
import subprocess
import threading
from pathlib import Path

import pytest

os.environ.setdefault("BOT_TOKEN", "1:test")


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory) -> Path:
    """A 30 s 720x1280 H.264 video with audio, and an audio-less one."""
    d = tmp_path_factory.mktemp("media")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=30:duration=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(d / "clip.mp4"),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "silent.mp4"),
    ], check=True)
    return d


@pytest.fixture(scope="session")
def http_base(media_dir) -> str:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(media_dir))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    from bot import config as cfg

    monkeypatch.setattr(cfg.config, "data_dir", tmp_path, raising=False)
    return tmp_path


@pytest.fixture(autouse=True)
def no_mp3_sites(monkeypatch):
    """Tests never touch the real MP3 catalogue sites (individual tests override this)."""
    from bot.services import downloader, mp3sites

    def offline(query):
        raise RuntimeError("all mp3 mirrors failed: offline in tests")

    monkeypatch.setattr(mp3sites, "search_sync", offline)
    from bot.services import ytalt

    monkeypatch.setattr(ytalt, "instances", lambda: [])
    monkeypatch.setattr(ytalt, "_down_until", 0.0)
    monkeypatch.setattr(downloader, "_yt_blocked_until", 0.0)
