"""🎧 Telegram Mini App: a player inside Telegram (search, favorites, playlists).

The bot serves the page and a small JSON API on WEBAPP_PORT (8080). Telegram needs HTTPS:
- WEBAPP_URL in .env -> your own https address (domain + reverse proxy), or
- docker-compose runs a free Cloudflare quick tunnel (cloudflared) and the bot reads its
  https://xxx.trycloudflare.com address by itself and puts it on the bot's menu button.
  The address changes when the tunnel restarts; the bot notices and updates the button.
Requests are authenticated with Telegram's signed initData (no logins).
"""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import MenuButtonDefault, MenuButtonWebApp, WebAppInfo
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiohttp import web

from ..common import send_song, send_track, split_query
from ..config import config
from ..db import DB
from ..services import charts, downloader, lyrics
from ..services.mp3sites import http_get
from ..texts import t

log = logging.getLogger(__name__)

HERE = Path(__file__).parent
# cover art the page may read pixels from (for colours) through /api/cover
COVER_HOSTS = ("i.ytimg.com", ".mzstatic.com", ".dzcdn.net")
STREAM_TTL = 6 * 3600
_state: dict = {"url": ""}


def public_url() -> str:
    return _state["url"]


def _sign(file_id: str) -> str:
    return hmac.new(config.bot_token.encode(), file_id.encode(), hashlib.sha256).hexdigest()[:32]


def stream_url(file_id: str) -> str:
    return f"/api/stream?f={file_id}&s={_sign(file_id)}"


class Api:
    def __init__(self, bot: Bot, db: DB):
        self.bot, self.db = bot, db
        self.cache = config.tmp_dir.parent / "stream"
        self.cache.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    # -------------------------------------------------------------- auth
    def user(self, request: web.Request) -> tuple[int, str]:
        init = request.headers.get("X-Init-Data") or request.query.get("init") or ""
        try:
            data = safe_parse_webapp_init_data(config.bot_token, init)
        except ValueError:
            raise web.HTTPUnauthorized(text="bad initData")
        if not data.user or (data.auth_date and time.time() - data.auth_date.timestamp() > 7 * 86400):
            raise web.HTTPUnauthorized(text="expired")
        return data.user.id, (data.user.language_code or "ru")[:2]

    async def lang_of(self, uid: int, tg_lang: str) -> str:
        return await self.db.get_lang(uid) or ("uz" if tg_lang == "uz" else "en" if tg_lang == "en" else "ru")

    # -------------------------------------------------------------- routes
    async def index(self, request: web.Request) -> web.Response:
        return web.FileResponse(HERE / "index.html", headers={"Cache-Control": "no-cache"})

    async def me(self, request: web.Request) -> web.Response:
        uid, tg_lang = self.user(request)
        likes = await self.db.get_likes(uid)
        playlists = []
        for p in await self.db.playlists_of(uid):
            playlists.append({"id": p["id"], "name": p["name"], "code": p["code"],
                              "items": await self.db.playlist_items(p["id"])})
        return web.json_response({"lang": await self.lang_of(uid, tg_lang), "likes": likes, "playlists": playlists})

    async def search(self, request: web.Request) -> web.Response:
        self.user(request)
        q = " ".join((request.query.get("q") or "").split())[:100]
        if len(q) < 2:
            return web.json_response({"items": []})
        lib = await self.db.search_library(q, limit=5)
        tracks = await downloader.search(q, limit=25)
        items = lib + [{"id": tr.id, "title": downloader.clean_title(tr.title) or tr.title,
                        "duration": tr.duration} for tr in tracks]
        return web.json_response({"items": items})

    async def chart(self, request: web.Request) -> web.Response:
        """Fresh charts for the home screen: ?kind=world|uz|ru."""
        self.user(request)
        kind = request.query.get("kind", "world")
        if kind not in charts.KINDS:
            raise web.HTTPNotFound()
        try:
            items = await asyncio.wait_for(charts.get_chart(kind), 60)
        except asyncio.TimeoutError:
            items = []
        return web.json_response({"items": items[:50]})

    async def playlist(self, request: web.Request) -> web.Response:
        self.user(request)
        pl = await self.db.get_playlist(code=request.match_info["code"])
        if not pl:
            raise web.HTTPNotFound()
        return web.json_response({"name": pl["name"], "items": await self.db.playlist_items(pl["id"])})

    async def play(self, request: web.Request) -> web.Response:
        """id -> a stream URL. fid:<file_id> plays at once; a YouTube / chart track is fetched first
        (it also arrives in the user's chat with the bot, so they keep it)."""
        uid, tg_lang = self.user(request)
        body = await request.json()
        tid = str(body.get("id") or "")
        title = str(body.get("title") or "")
        lang = await self.lang_of(uid, tg_lang)
        if tid.startswith("fid:"):
            return web.json_response({"url": stream_url(tid[4:]), "fid": tid[4:]})
        cached = await self.db.get_file(f"a:{tid}") if not tid.startswith("q:") else None
        if cached:
            return web.json_response({"url": stream_url(cached[1]), "fid": cached[1]})
        try:
            if tid.startswith("q:"):
                name, artist = split_query(tid[2:])
                msg = await send_song(self.bot, self.db, uid, name, artist, lang)
            else:
                msg = await send_track(self.bot, self.db, uid, tid, lang, query=downloader.clean_title(title))
        except downloader.DownloadFailed:
            return web.json_response({"error": t(lang, "track_failed")}, status=502)
        except Exception:
            log.exception("webapp play failed")
            return web.json_response({"error": t(lang, "error")}, status=500)
        if not msg.audio:
            return web.json_response({"error": t(lang, "error")}, status=500)
        return web.json_response({"url": stream_url(msg.audio.file_id), "fid": msg.audio.file_id, "sent": True})

    async def like(self, request: web.Request) -> web.Response:
        """❤️ from the player: toggles a like on a track the user already has (fid:<file_id>)."""
        uid, _ = self.user(request)
        body = await request.json()
        fid = str(body.get("id") or "").removeprefix("fid:")
        if not fid:
            raise web.HTTPBadRequest()
        if await self.db.unlike_file(uid, fid):
            return web.json_response({"liked": False})
        try:
            unique = (await self.bot.get_file(fid)).file_unique_id
        except Exception:  # noqa: BLE001  (big files can't be fetched by getFile; the file id still works)
            unique = fid
        await self.db.toggle_like(uid, unique, fid, str(body.get("title") or "♪")[:200], int(body.get("duration") or 0))
        return web.json_response({"liked": True})

    async def song_lyrics(self, request: web.Request) -> web.Response:
        """Lyrics for the player: time-stamped lines when LRCLIB has them, plain text otherwise."""
        self.user(request)
        name = " ".join((request.query.get("title") or "").split())[:200]
        if not name:
            return web.json_response({"synced": None, "text": None})
        key = "lyw:" + name.lower()
        cached = await self.db.get_file(key)
        if cached:
            return web.json_response(cached[2])
        performer, _, title = name.partition(" - ")
        if not title:
            performer, title = "", performer
        title = downloader.clean_title(title) or title
        synced = await asyncio.to_thread(lyrics.find_synced, title, performer)
        text = None if synced else await asyncio.to_thread(lyrics.find, title, performer)
        data = {"synced": synced, "text": text}
        if synced or text:
            await self.db.put_file(key, "lyrics", "-", data)
        return web.json_response(data)

    async def cover(self, request: web.Request) -> web.Response:
        """Same-origin copy of a cover so the page can pick its colours (canvas needs CORS)."""
        url = request.query.get("u", "")
        host = url.split("/")[2] if url.startswith("https://") and url.count("/") >= 3 else ""
        if not host or not any(host == h or (h.startswith(".") and host.endswith(h)) for h in COVER_HOSTS):
            raise web.HTTPForbidden()
        try:
            data = await asyncio.to_thread(http_get, url, timeout=10)
        except Exception:  # noqa: BLE001
            raise web.HTTPNotFound()
        return web.Response(body=data[:2_000_000], content_type="image/jpeg",
                            headers={"Cache-Control": "public, max-age=604800"})

    async def stream(self, request: web.Request) -> web.StreamResponse:
        fid, sig = request.query.get("f", ""), request.query.get("s", "")
        if not fid or not hmac.compare_digest(sig, _sign(fid)):
            raise web.HTTPForbidden()
        path = self.cache / (hashlib.sha1(fid.encode()).hexdigest() + ".mp3")
        lock = self._locks.setdefault(path.name, asyncio.Lock())
        async with lock:
            if not path.exists():
                tmp = path.with_suffix(".part")
                try:
                    await self.bot.download(fid, destination=tmp, timeout=300)
                except TelegramBadRequest:
                    raise web.HTTPNotFound()
                tmp.rename(path)
        self._locks.pop(path.name, None)
        path.touch()
        # FileResponse answers Range requests, which iOS needs to play audio
        return web.FileResponse(path, headers={"Content-Type": "audio/mpeg", "Cache-Control": "private, max-age=86400"})


def make_app(bot: Bot, db: DB) -> web.Application:
    api = Api(bot, db)
    app = web.Application(client_max_size=64 * 1024)
    app.router.add_get("/", api.index)
    app.router.add_get("/api/me", api.me)
    app.router.add_get("/api/search", api.search)
    app.router.add_get("/api/playlist/{code}", api.playlist)
    app.router.add_get("/api/chart", api.chart)
    app.router.add_post("/api/play", api.play)
    app.router.add_get("/api/stream", api.stream)
    app.router.add_post("/api/like", api.like)
    app.router.add_get("/api/lyrics", api.song_lyrics)
    app.router.add_get("/api/cover", api.cover)
    app["api"] = api
    return app


def _quick_tunnel_url() -> str:
    """https address of the cloudflared quick tunnel (its metrics server reports the hostname)."""
    if not config.tunnel_metrics:
        return ""
    try:
        data = json.loads(http_get(config.tunnel_metrics.rstrip("/") + "/quicktunnel", timeout=5))
    except Exception as e:  # noqa: BLE001
        log.warning("Mini App: cloudflared tunnel not ready: %s", str(e)[:120])
        return ""
    host = (data or {}).get("hostname") or ""
    return f"https://{host}" if host else ""


async def refresh_url(bot: Bot) -> str:
    url = config.webapp_url or await asyncio.to_thread(_quick_tunnel_url)
    if url and url != _state["url"]:
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text=t("ru", "app_menu"), web_app=WebAppInfo(url=url)))
            log.info("Mini App at %s", url)
            _state["url"] = url
        except TelegramBadRequest as e:
            log.warning("could not set the Mini App menu button: %s", e)
    elif not url and _state["url"]:
        _state["url"] = ""
        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        except TelegramBadRequest:
            pass
    return _state["url"]


async def run(bot: Bot, db: DB) -> None:
    """Serve the Mini App and keep the menu button pointing at its current https address."""
    if not config.webapp_port:
        return
    runner = web.AppRunner(make_app(bot, db), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.webapp_port).start()
    log.info("Mini App server on port %d", config.webapp_port)
    stream_dir = config.tmp_dir.parent / "stream"
    try:
        while True:
            try:
                await refresh_url(bot)
                from ..utils import cleanup_old
                cleanup_old(stream_dir, max_age=STREAM_TTL)
            except Exception:
                log.exception("Mini App refresh failed")
            # the tunnel needs ~10-30 s after start: look often until it is up, then every 5 minutes
            await asyncio.sleep(10 if not _state["url"] else 300)
    finally:
        await runner.cleanup()
