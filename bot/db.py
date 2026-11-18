"""Small SQLite store: users, language, Telegram file_id cache, saved searches, stats."""
import json
import time
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    lang TEXT,
    created INTEGER
);
CREATE TABLE IF NOT EXISTS file_cache (
    key TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    file_id TEXT NOT NULL,
    meta TEXT,
    created INTEGER
);
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    results TEXT NOT NULL,
    created INTEGER
);
CREATE TABLE IF NOT EXISTS stats (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
"""


class DB:
    def __init__(self, path: Path):
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.executescript(SCHEMA)
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    # users
    async def get_lang(self, user_id: int) -> str | None:
        async with self.conn.execute("SELECT lang FROM users WHERE id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        return row[0] if row else None

    async def ensure_user(self, user_id: int, lang: str) -> str:
        existing = await self.get_lang(user_id)
        if existing:
            return existing
        await self.conn.execute(
            "INSERT OR IGNORE INTO users(id, lang, created) VALUES(?,?,?)", (user_id, lang, int(time.time()))
        )
        await self.conn.commit()
        return lang

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.conn.execute(
            "INSERT INTO users(id, lang, created) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET lang=excluded.lang",
            (user_id, lang, int(time.time())),
        )
        await self.conn.commit()

    async def count_users(self) -> int:
        async with self.conn.execute("SELECT COUNT(*) FROM users") as cur:
            return (await cur.fetchone())[0]

    # file_id cache: the same track/video is sent instantly the second time
    async def get_file(self, key: str) -> tuple[str, str, dict] | None:
        async with self.conn.execute("SELECT kind, file_id, meta FROM file_cache WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return row[0], row[1], json.loads(row[2] or "{}")

    async def put_file(self, key: str, kind: str, file_id: str, meta: dict | None = None) -> None:
        await self.conn.execute(
            "INSERT OR REPLACE INTO file_cache(key, kind, file_id, meta, created) VALUES(?,?,?,?,?)",
            (key, kind, file_id, json.dumps(meta or {}, ensure_ascii=False), int(time.time())),
        )
        await self.conn.commit()

    async def drop_file(self, key: str) -> None:
        await self.conn.execute("DELETE FROM file_cache WHERE key=?", (key,))
        await self.conn.commit()

    # searches (so pagination / buttons keep working after restarts)
    async def save_search(self, query: str, results: list[dict]) -> int:
        cur = await self.conn.execute(
            "INSERT INTO searches(query, results, created) VALUES(?,?,?)",
            (query, json.dumps(results, ensure_ascii=False), int(time.time())),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_search(self, search_id: int) -> tuple[str, list[dict]] | None:
        async with self.conn.execute("SELECT query, results FROM searches WHERE id=?", (search_id,)) as cur:
            row = await cur.fetchone()
        return (row[0], json.loads(row[1])) if row else None

    async def prune_searches(self, max_age: int = 7 * 86400) -> None:
        await self.conn.execute("DELETE FROM searches WHERE created < ?", (int(time.time()) - max_age,))
        await self.conn.commit()

    # stats
    async def incr(self, name: str) -> None:
        await self.conn.execute(
            "INSERT INTO stats(name, value) VALUES(?, 1) ON CONFLICT(name) DO UPDATE SET value = value + 1", (name,)
        )
        await self.conn.commit()

    async def get_stat(self, name: str) -> int:
        async with self.conn.execute("SELECT value FROM stats WHERE name=?", (name,)) as cur:
            row = await cur.fetchone()
        return row[0] if row else 0
