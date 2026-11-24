import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from .db import DB
from .texts import guess_lang

TOUCH_EVERY = 300  # seconds between "last seen" writes per user


class LangMiddleware(BaseMiddleware):
    """Registers the user, tracks activity and injects `lang` and `db` into handlers."""

    def __init__(self, db: DB):
        self.db = db
        self._touched: dict[int, float] = {}

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        data["db"] = self.db
        if user and not user.is_bot:
            data["lang"] = await self.db.ensure_user(user.id, guess_lang(user.language_code))
            now = time.time()
            if now - self._touched.get(user.id, 0) > TOUCH_EVERY:
                self._touched[user.id] = now
                await self.db.touch(user.id)
        else:
            data["lang"] = "ru"
        return await handler(event, data)
