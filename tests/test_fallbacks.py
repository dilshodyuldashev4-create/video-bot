"""Blocked server IP: direct -> proxy fallback, and YouTube -> SoundCloud fallback."""
import yt_dlp

from bot.config import config
from bot.services import downloader

BOT_CHECK = "ERROR: [youtube] U3kf72Zw3yA: Sign in to confirm you're not a bot."


class FakeYDL:
    calls: list[dict] = []
    fail_direct = True

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        FakeYDL.calls.append({"url": url, "proxy": self.opts.get("proxy")})
        if FakeYDL.fail_direct and not self.opts.get("proxy"):
            raise yt_dlp.utils.DownloadError(BOT_CHECK)
        return {"id": "x", "title": "ok"}


def _setup(monkeypatch, proxy="socks5://warp:1080"):
    FakeYDL.calls = []
    FakeYDL.fail_direct = True
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(config, "proxy", proxy)
    downloader._proxy_first_until.clear()


def test_falls_back_to_proxy_and_remembers(monkeypatch):
    _setup(monkeypatch)
    url = "https://www.youtube.com/watch?v=U3kf72Zw3yA"
    assert downloader._extract(url, {})["title"] == "ok"
    assert [c["proxy"] for c in FakeYDL.calls] == [None, "socks5://warp:1080"]
    # next YouTube request goes through the proxy first, no wasted direct attempt
    FakeYDL.calls = []
    downloader._extract("ytsearch5:Dior", {}, download=False)
    assert [c["proxy"] for c in FakeYDL.calls] == ["socks5://warp:1080"]
    # other sites are unaffected
    FakeYDL.calls = []
    FakeYDL.fail_direct = False
    downloader._extract("https://www.tiktok.com/@a/video/1", {})
    assert [c["proxy"] for c in FakeYDL.calls] == [None]


def test_no_proxy_configured_raises_original_error(monkeypatch):
    _setup(monkeypatch, proxy="")
    try:
        downloader._extract("https://youtu.be/U3kf72Zw3yA", {})
    except yt_dlp.utils.DownloadError as e:
        assert "not a bot" in str(e)
    else:
        raise AssertionError("should raise")
    assert len(FakeYDL.calls) == 1


def test_permanent_errors_are_not_retried(monkeypatch):
    _setup(monkeypatch)

    class Private(FakeYDL):
        def extract_info(self, url, download=True):
            FakeYDL.calls.append(1)
            raise yt_dlp.utils.DownloadError("ERROR: [youtube] x: Private video. Sign in if you've been granted access")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", Private)
    try:
        downloader._extract("https://youtu.be/x", {})
    except yt_dlp.utils.DownloadError:
        pass
    assert FakeYDL.calls == [1]


def test_clean_title():
    assert downloader.clean_title("POP SMOKE - DIOR (OFFICIAL VIDEO)") == "POP SMOKE - DIOR"
    assert downloader.clean_title(
        "Dior Sergeli - Kim Bo'ldin 2023(Uzmix Remix) @UZMIXBEATS #zohid #music") == \
        "Dior Sergeli - Kim Bo'ldin 2023(Uzmix Remix)"
    assert downloader.clean_title("Dior feat. Davrick - Prapiskela qatta (official hd video)") == \
        "Dior feat. Davrick - Prapiskela qatta"


def test_site():
    assert downloader._site("https://youtu.be/x") == "youtube"
    assert downloader._site("https://m.youtube.com/watch?v=x") == "youtube"
    assert downloader._site("ytsearch3:abc") == "youtube"
    assert downloader._site("https://vm.tiktok.com/x") == "tiktok"


def test_soundcloud_picks_matching_track(monkeypatch, tmp_path):
    _setup(monkeypatch, proxy="")
    downloaded = []

    class SC(FakeYDL):
        def extract_info(self, url, download=True):
            if url.startswith("scsearch"):
                return {"entries": [
                    {"url": "https://soundcloud.com/a/karaoke", "title": "Some karaoke", "uploader": "x"},
                    {"url": "https://soundcloud.com/popsmoke/dior", "title": "Dior", "uploader": "POP SMOKE"},
                ]}
            downloaded.append(url)
            return {"id": "dior", "title": "Dior"}

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", SC)
    downloader._soundcloud_sync("POP SMOKE - DIOR", tmp_path)
    assert downloaded == ["https://soundcloud.com/popsmoke/dior"]


def test_pot_provider_args_are_valid(monkeypatch, http_base, tmp_path):
    """The real yt-dlp accepts our PO-token extractor args (plugin installed)."""
    monkeypatch.setattr(config, "pot_url", "http://127.0.0.1:1")
    opts = downloader._audio_opts(tmp_path)
    assert opts["extractor_args"]["youtubepot-bgutilhttp"]["base_url"] == ["http://127.0.0.1:1"]
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"{http_base}/clip.mp4", download=True)
    assert info and list(tmp_path.glob("*.mp3"))


def test_soundcloud_skips_drm_tracks(monkeypatch, tmp_path):
    _setup(monkeypatch, proxy="")
    tried = []

    class SC(FakeYDL):
        def extract_info(self, url, download=True):
            if url.startswith("scsearch"):
                return {"entries": [
                    {"url": "https://soundcloud.com/popsmoke/dior", "title": "Dior", "uploader": "POP SMOKE"},
                    {"url": "https://soundcloud.com/fan/dior", "title": "dior live", "uploader": "fan"},
                ]}
            tried.append(url)
            if url.endswith("popsmoke/dior"):
                raise yt_dlp.utils.DownloadError("ERROR: [soundcloud] 656255261: This video is DRM protected")
            return {"id": "ok", "title": "Dior"}

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", SC)
    assert downloader._soundcloud_sync("POP SMOKE - DIOR", tmp_path)["id"] == "ok"
    assert len(tried) == 2
