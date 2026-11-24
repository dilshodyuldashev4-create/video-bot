"""Small SQLite store: users, admins, language, file_id cache, saved searches, likes, stats."""
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
CREATE TABLE IF NOT EXISTS likes (
    user_id INTEGER NOT NULL,
    unique_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    title TEXT,
    duration INTEGER,
    created INTEGER,
    PRIMARY KEY (user_id, unique_id)
);
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY,
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
        # migrations for databases created by older versions
        async with self.conn.execute("PRAGMA table_info(users)") as cur:
            cols = {row[1] for row in await cur.fetchall()}
        for col, ddl in (("last_seen", "INTEGER"), ("blocked", "INTEGER NOT NULL DEFAULT 0")):
            if col not in cols:
                await self.conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
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

    async def touch(self, user_id: int) -> None:
        """Mark the user active now (they also unblocked the bot if they write to it)."""
        await self.conn.execute("UPDATE users SET last_seen=?, blocked=0 WHERE id=?", (int(time.time()), user_id))
        await self.conn.commit()

    async def set_blocked(self, user_id: int) -> None:
        await self.conn.execute("UPDATE users SET blocked=1 WHERE id=?", (user_id,))
        await self.conn.commit()

    async def broadcast_ids(self) -> list[int]:
        async with self.conn.execute("SELECT id FROM users WHERE blocked=0 AND id > 0 ORDER BY id") as cur:
            return [r[0] for r in await cur.fetchall()]

    async def _scalar(self, sql: str, *args) -> int:
        async with self.conn.execute(sql, args) as cur:
            row = await cur.fetchone()
        return int(row[0] or 0) if row else 0

    async def user_stats(self) -> dict:
        now = int(time.time())
        day, week = now - 86400, now - 7 * 86400
        stats = {
            "total": await self._scalar("SELECT COUNT(*) FROM users"),
            "new_day": await self._scalar("SELECT COUNT(*) FROM users WHERE created >= ?", day),
            "new_week": await self._scalar("SELECT COUNT(*) FROM users WHERE created >= ?", week),
            "active_day": await self._scalar("SELECT COUNT(*) FROM users WHERE last_seen >= ?", day),
            "active_week": await self._scalar("SELECT COUNT(*) FROM users WHERE last_seen >= ?", week),
            "blocked": await self._scalar("SELECT COUNT(*) FROM users WHERE blocked = 1"),
            "likes": await self._scalar("SELECT COUNT(*) FROM likes"),
            "searches_week": await self._scalar(
                "SELECT COUNT(*) FROM searches WHERE created >= ? AND query NOT LIKE '\\_\\_%' ESCAPE '\\'", week),
        }
        async with self.conn.execute("SELECT lang, COUNT(*) FROM users GROUP BY lang") as cur:
            stats["langs"] = {r[0] or "?": r[1] for r in await cur.fetchall()}
        return stats

    async def top_queries(self, days: int = 7, limit: int = 15) -> list[tuple[str, int]]:
        since = int(time.time()) - days * 86400
        async with self.conn.execute(
            "SELECT lower(query) q, COUNT(*) c FROM searches WHERE created >= ? "
            "AND query NOT LIKE '\\_\\_%' ESCAPE '\\' GROUP BY q ORDER BY c DESC LIMIT ?",
            (since, limit),
        ) as cur:
            return [(r[0], r[1]) for r in await cur.fetchall()]

    # admins (in addition to ADMIN_IDS from .env)
    async def admin_ids(self) -> set[int]:
        async with self.conn.execute("SELECT id FROM admins") as cur:
            return {r[0] for r in await cur.fetchall()}

    async def add_admin(self, user_id: int) -> None:
        await self.conn.execute("INSERT OR IGNORE INTO admins(id, created) VALUES(?,?)", (user_id, int(time.time())))
        await self.conn.commit()

    async def remove_admin(self, user_id: int) -> None:
        await self.conn.execute("DELETE FROM admins WHERE id=?", (user_id,))
        await self.conn.commit()

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

    # likes ("My music" playlist)
    async def toggle_like(self, user_id: int, unique_id: str, file_id: str, title: str, duration: int) -> bool:
        """Returns True if the track is now liked, False if the like was removed."""
        cur = await self.conn.execute("DELETE FROM likes WHERE user_id=? AND unique_id=?", (user_id, unique_id))
        if cur.rowcount:
            await self.conn.commit()
            return False
        await self.conn.execute(
            "INSERT INTO likes(user_id, unique_id, file_id, title, duration, created) VALUES(?,?,?,?,?,?)",
            (user_id, unique_id, file_id, title, duration, int(time.time())),
        )
        await self.conn.commit()
        return True

    async def is_liked(self, user_id: int, unique_id: str) -> bool:
        async with self.conn.execute(
            "SELECT 1 FROM likes WHERE user_id=? AND unique_id=?", (user_id, unique_id)
        ) as cur:
            return await cur.fetchone() is not None

    async def get_likes(self, user_id: int, limit: int = 100) -> list[dict]:
        async with self.conn.execute(
            "SELECT file_id, title, duration FROM likes WHERE user_id=? ORDER BY created DESC LIMIT ?",
            (user_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [{"id": f"fid:{r[0]}", "title": r[1] or "♪", "duration": r[2] or 0} for r in rows]

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
