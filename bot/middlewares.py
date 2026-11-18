from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from .db import DB
from .texts import guess_lang


class LangMiddleware(BaseMiddleware):
    """Registers the user and injects `lang` and `db` into handlers."""

    def __init__(self, db: DB):
        self.db = db

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        data["db"] = self.db
        data["lang"] = await self.db.ensure_user(user.id, guess_lang(user.language_code)) if user else "ru"
        return await handler(event, data)
