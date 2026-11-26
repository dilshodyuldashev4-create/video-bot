"""Entry point: python -m bot"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import config
from .db import DB
from .handlers import admin, inline, library, links, music, recognize, search, start, tools
from .middlewares import LangMiddleware
from .services import downloader, updater
from .utils import cleanup_old

log = logging.getLogger("bot")


async def housekeeping(db: DB) -> None:
    while True:
        try:
            cleanup_old(config.tmp_dir, max_age=2 * 3600)
            cleanup_old(config.data_dir / "clips", max_age=48 * 3600)
            await db.prune_searches()
            ok = await asyncio.to_thread(downloader.probe_youtube_sync)
            log.info("YouTube from this server: %s", "OK" if ok else "blocked, using helpers")
        except Exception:
            log.exception("housekeeping failed")
        await asyncio.sleep(1800)


def build_dispatcher(db: DB) -> Dispatcher:
    dp = Dispatcher()
    mw = LangMiddleware(db)
    dp.message.outer_middleware(mw)
    dp.callback_query.outer_middleware(mw)
    dp.inline_query.outer_middleware(mw)
    dp.chosen_inline_result.outer_middleware(mw)
    # order matters: commands, then links, then media, then plain text = search
    dp.include_routers(admin.router, music.router, start.router, inline.router, library.router, links.router, recognize.router,
                       tools.router, search.router)
    return dp


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if not config.bot_token:
        sys.exit("BOT_TOKEN is not set (see .env.example)")
    config.tmp_dir.mkdir(parents=True, exist_ok=True)

    session = None
    if config.local_api:
        session = AiohttpSession(api=TelegramAPIServer.from_base(config.api_url, is_local=True))
    bot = Bot(config.bot_token, session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    db = DB(config.db_path)
    await db.connect()
    dp = build_dispatcher(db)

    await bot.set_my_commands([
        BotCommand(command="start", description="🏠 Start / Старт"),
        BotCommand(command="mymusic", description="❤️ My music / Моя музыка"),
        BotCommand(command="app", description="🎧 Player / Плеер"),
        BotCommand(command="playlists", description="📂 Playlists / Плейлисты"),
        BotCommand(command="follows", description="🔔 Artists I follow / Мои артисты"),
        BotCommand(command="mood", description="🎧 Mood / Настроение"),
        BotCommand(command="wrapped", description="📊 My year / Мой год"),
        BotCommand(command="help", description="📖 Help / Помощь"),
        BotCommand(command="lang", description="🌐 Language / Til / Язык"),
    ])
    from .webapp import server as webapp
    tasks = [asyncio.create_task(housekeeping(db)), asyncio.create_task(music.release_watcher(bot, db)),
             asyncio.create_task(webapp.run(bot, db)),
             asyncio.create_task(updater.run(lambda: downloader.active_downloads() > 0))]
    me = await bot.me()
    log.info("yt-dlp %s", updater.installed())
    log.info("Started @%s (local API: %s, upload limit %d MB)", me.username, config.local_api,
             config.upload_limit // 2**20)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
