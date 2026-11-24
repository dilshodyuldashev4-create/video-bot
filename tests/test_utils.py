from bot.keyboards import results_kb, results_text
from bot.services.downloader import similarity, split_title
from bot.services.recognizer import SEGMENT, segment_offsets
from bot.texts import guess_lang, t
from bot.utils import canonical_key, detect_platform, extract_url, fmt_duration


def test_detect_platform():
    cases = {
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ": "youtube",
        "https://youtu.be/dQw4w9WgXcQ?si=x": "youtube",
        "https://youtube.com/shorts/abcdefghijk": "youtube",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ": "youtube",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ": "youtube",
        "https://www.instagram.com/reel/C1abcDEF/?igsh=xyz": "instagram",
        "https://instagram.com/p/C1abcDEF/": "instagram",
        "https://vm.tiktok.com/ZMabc123/": "tiktok",
        "https://www.tiktok.com/@user/video/7300000000000000000": "tiktok",
        "https://example.com/video.mp4": None,
        "https://notyoutube.com/watch": None,
    }
    for url, expected in cases.items():
        assert detect_platform(url) == expected, url


def test_extract_url():
    assert extract_url("смотри https://youtu.be/dQw4w9WgXcQ!") == "https://youtu.be/dQw4w9WgXcQ"
    assert extract_url("Dior") is None


def test_canonical_key():
    a = canonical_key("https://youtu.be/dQw4w9WgXcQ?si=1", "youtube")
    b = canonical_key("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", "youtube")
    c = canonical_key("https://youtube.com/shorts/dQw4w9WgXcQ", "youtube")
    assert a == b == c == "youtube:dQw4w9WgXcQ"
    assert canonical_key("https://www.instagram.com/reel/ABC/?igsh=1", "instagram") == \
        canonical_key("https://instagram.com/reel/ABC", "instagram")


def test_fmt_duration():
    assert fmt_duration(170) == "2:50"
    assert fmt_duration(3725) == "1:02:05"
    assert fmt_duration(None) == ""


def test_split_title():
    assert split_title({"title": "POP SMOKE - DIOR (OFFICIAL VIDEO)"}) == ("POP SMOKE", "DIOR")
    assert split_title({"title": "Dior", "track": "Dior", "artist": "Pop Smoke"}) == ("Pop Smoke", "Dior")
    assert split_title({"title": "Dior (Official Audio)", "uploader": "Pop Smoke - Topic"}) == ("Pop Smoke", "Dior")


def test_similarity():
    assert similarity("Pop Smoke - Dior", "POP SMOKE - DIOR") > 0.95
    assert similarity("Pop Smoke - Dior", "Rick Astley - Never") < 0.5


def test_segment_offsets():
    assert segment_offsets(8) == [0.0]
    offs = segment_offsets(180)
    assert 3 <= len(offs) <= 5
    assert all(0 <= o <= 180 - SEGMENT for o in offs)
    assert offs[0] > 0  # middle first: reels often start with talking
    assert 0.0 in offs


def test_results_keyboard_layout():
    results = [{"id": str(i), "title": f"Song {i}", "duration": 120} for i in range(23)]
    kb = results_kb(5, len(results), 0).inline_keyboard
    assert [b.text for b in kb[0]] == ["1", "2", "3", "4", "5"]
    assert [b.text for b in kb[1]] == ["6", "7", "8", "9", "10"]
    assert [b.text for b in kb[-1]] == ["⬅️", "❌", "➡️"]
    assert kb[-1][0].callback_data == "p:5:2"  # wraps to last page
    last = results_kb(5, len(results), 2).inline_keyboard
    assert [b.text for b in last[0]] == ["1", "2", "3"]
    assert last[0][0].callback_data == "t:5:20"
    assert last[-1][2].callback_data == "p:5:0"
    text = results_text("Dior & <b>", results, 0, "ru")
    assert "&lt;b&gt;" in text and "<b>10.</b> Song 9 · <b>2:00</b>" in text and "стр. 1/3" in text


def test_texts():
    assert guess_lang("uz") == "uz" and guess_lang("ru") == "ru" and guess_lang(None) == "ru"
    for lang in ("ru", "uz"):
        assert "@x" in t(lang, "audio_footer", bot="x")
        assert "@x" in t(lang, "video_caption", icon="▶️", platform="YouTube", bot="x")


def test_three_languages_have_the_same_keys():
    from bot.texts import LANGS, TEXTS
    assert set(LANGS) == set(TEXTS) == {"uz", "ru", "en"}
    keys = set(TEXTS["ru"])
    for lang, table in TEXTS.items():
        assert set(table) == keys, lang


def test_guess_lang_three():
    assert guess_lang("uz") == "uz" and guess_lang("en-GB") == "en" and guess_lang("ru") == "ru"
    assert guess_lang("de") == "ru"


def test_mp3site_parser_and_pick():
    from bot.services import mp3sites

    page = '''
    <ul class="tracks__list">
    <li class="tracks__item track mustoggler" itemprop="track"
        data-musmeta='{"artist":"UzBoom","title":"Kecholmadim","url":"https:\\/\\/s.example\\/get\\/music\\/1.mp3","img":"\\/img\\/1.jpg"}'>
      <div class="track__title">Kecholmadim</div>
    </li>
    <li class="tracks__item track mustoggler">
      <div class="track__info"><a href="/song/2"><div class="track__title"> Kecholmadim (Remix) </div>
      <div class="track__desc">DJ &amp; UzBoom</div></a></div>
      <div class="track__fulltime">03:21</div>
      <a href="/get/music/2.mp3" class="track__download-btn" download>dl</a>
    </li>
    <li class="tracks__item track"><div class="track__title">Boshqa</div>
      <div class="track__desc">Other</div><a class="track__download-btn" href="https://s.example/3.mp3">x</a></li>
    </ul>'''
    tracks = mp3sites.parse_search(page, "https://rus.hitmotop.com")
    assert [(t.artist, t.title) for t in tracks] == [
        ("UzBoom", "Kecholmadim"), ("DJ & UzBoom", "Kecholmadim (Remix)"), ("Other", "Boshqa")]
    assert tracks[0].url == "https://s.example/get/music/1.mp3"
    assert tracks[0].cover == "https://rus.hitmotop.com/img/1.jpg"
    assert tracks[1].url == "https://rus.hitmotop.com/get/music/2.mp3" and tracks[1].duration == 201
    picked = mp3sites.pick(tracks, "Kecholmadim", "UzBoom")
    assert [t.title for t in picked] == ["Kecholmadim", "Kecholmadim (Remix)"]  # unrelated dropped, remix last


def test_lyrics_sources(monkeypatch):
    import json as _json

    from bot.services import lyrics

    page = ('<div data-lyrics-container="true">[Verse 1]<br/>Ko&#x27;zlaring <i>yulduz</i><br>'
            '<div data-exclude-from-selection="true">Embed</div>Kecholmadim</div>'
            '<div>ads</div><div data-lyrics-container="true">Chorus line</div>')
    assert lyrics.parse_genius_page(page) == "[Verse 1]\nKo'zlaring yulduz\nKecholmadim\nChorus line"

    def fake_get(url, **kw):
        if "lrclib" in url:
            return _json.dumps([{"trackName": "Other song", "artistName": "X", "plainLyrics": "nope"},
                                {"trackName": "Kecholmadim", "artistName": "UzBoom",
                                 "syncedLyrics": "[00:01.00] line one\n[00:05.20] line two"}]).encode()
        raise OSError("offline")

    monkeypatch.setattr(lyrics, "http_get", fake_get)
    assert lyrics.find("Kecholmadim (Official Video)", "UzBoom") == "line one\nline two"
    assert lyrics.find("Unknown", "Nobody") is None
