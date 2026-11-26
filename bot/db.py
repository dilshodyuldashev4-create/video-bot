"""Small SQLite store: users, admins, language, file_id cache, saved searches, likes, stats."""
import json
import re
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
CREATE TABLE IF NOT EXISTS library (
    unique_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    title TEXT,
    performer TEXT,
    duration INTEGER,
    norm TEXT,
    added_by INTEGER,
    created INTEGER
);
CREATE TABLE IF NOT EXISTS plays (
    user_id INTEGER NOT NULL,
    title TEXT,
    performer TEXT,
    created INTEGER
);
CREATE INDEX IF NOT EXISTS plays_user ON plays(user_id, created);
CREATE TABLE IF NOT EXISTS listens (
    user_id INTEGER NOT NULL,
    artist TEXT,
    title TEXT,
    kind TEXT,
    created INTEGER
);
CREATE INDEX IF NOT EXISTS listens_user ON listens(user_id, created);
CREATE TABLE IF NOT EXISTS follows (
    user_id INTEGER NOT NULL,
    artist_id TEXT NOT NULL,
    artist_name TEXT,
    created INTEGER,
    PRIMARY KEY (user_id, artist_id)
);
CREATE TABLE IF NOT EXISTS artist_state (
    artist_id TEXT PRIMARY KEY,
    release_id TEXT,
    release_title TEXT,
    checked INTEGER
);
CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    created INTEGER
);
CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id INTEGER NOT NULL,
    unique_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    title TEXT,
    duration INTEGER,
    created INTEGER,
    PRIMARY KEY (playlist_id, unique_id)
);
CREATE TABLE IF NOT EXISTS stats (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);
"""


def norm_text(text: str) -> str:
    """'Pop Smoke — DIOR (Official)' -> 'pop smoke dior official' (for library search)."""
    return " ".join(re.findall(r"\w+", (text or "").lower().replace("ё", "е")))


def _words(text: str) -> list[str]:
    return [w for w in norm_text(text).split() if len(w) >= 2][:8]


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

    async def unlike_file(self, user_id: int, file_id: str) -> bool:
        cur = await self.conn.execute("DELETE FROM likes WHERE user_id=? AND file_id=?", (user_id, file_id))
        await self.conn.commit()
        return bool(cur.rowcount)

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

    # music library: every MP3 users send or the bot sends, searchable by title / artist
    async def add_to_library(self, unique_id: str, file_id: str, title: str, performer: str,
                             duration: int, added_by: int | None = None) -> None:
        if not (title or performer):
            return
        await self.conn.execute(
            "INSERT INTO library(unique_id, file_id, title, performer, duration, norm, added_by, created) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(unique_id) DO UPDATE SET file_id=excluded.file_id",
            (unique_id, file_id, title or "", performer or "", duration or 0,
             norm_text(f"{performer} {title}"), added_by, int(time.time())),
        )
        await self.conn.commit()

    async def search_library(self, query: str, limit: int = 5) -> list[dict]:
        """Tracks whose artist + title contain every word of the query."""
        words = _words(query)
        if not words:
            return []
        where = " AND ".join("(' ' || norm || ' ') LIKE ?" for _ in words)
        args = [f"% {w}%" for w in words]
        async with self.conn.execute(
            f"SELECT file_id, title, performer, duration FROM library WHERE {where} "
            f"ORDER BY length(norm) ASC, created DESC LIMIT ?", (*args, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [{"id": f"fid:{r[0]}", "title": f"{r[2]} - {r[1]}" if r[2] else r[1], "duration": r[3] or 0,
                 "lib": True} for r in rows]

    async def library_count(self) -> int:
        return await self._scalar("SELECT COUNT(*) FROM library")

    async def find_in_library(self, title: str, artist: str) -> dict | None:
        """Exact-ish match for a known song (Shazam result, chart entry)."""
        t_words = _words(title)
        if not t_words:
            return None
        rows = await self.search_library(f"{artist} {title}", limit=1) if artist else []
        if not rows:
            rows = [r for r in await self.search_library(title, limit=10)
                    if not artist or set(_words(artist)) & set(_words(r["title"]))]
        return rows[0] if rows else None

    # plays: what each user got, for "Your year" (Wrapped)
    async def log_play(self, user_id: int, title: str, performer: str) -> None:
        if user_id <= 0 or not (title or performer):
            return
        await self.conn.execute("INSERT INTO plays(user_id, title, performer, created) VALUES(?,?,?,?)",
                                (user_id, title or "", performer or "", int(time.time())))
        await self.conn.commit()

    # listens: what the user does in the player (play / finish / skip), for the personal stream
    async def add_listen(self, user_id: int, artist: str, title: str, kind: str) -> None:
        await self.conn.execute("INSERT INTO listens(user_id, artist, title, kind, created) VALUES(?,?,?,?,?)",
                                (user_id, (artist or "")[:120], (title or "")[:200], kind, int(time.time())))
        await self.conn.commit()

    async def taste(self, user_id: int, days: int = 120) -> dict:
        """{'artists': [(name, score)...] best first, 'skipped': {titles}, 'recent': {titles}} from the
        player (finish +3, play +1, skip -3), tracks the bot sent (+1) and likes (+4)."""
        since = int(time.time()) - days * 86400
        score: dict[str, float] = {}
        names: dict[str, str] = {}
        skipped, recent = set(), set()

        def add(artist: str, pts: float) -> None:
            for a in re.split(r"\s*(?:,|&| feat\.? | ft\.? | x )\s*", artist or "", flags=re.I)[:2]:
                a = a.strip()
                if a:
                    k = a.lower()
                    names.setdefault(k, a)
                    score[k] = score.get(k, 0) + pts

        weights = {"finish": 3, "play": 1, "skip": -3}
        async with self.conn.execute("SELECT artist, title, kind FROM listens WHERE user_id=? AND created>=? "
                                     "ORDER BY created DESC LIMIT 2000", (user_id, since)) as cur:
            for i, (artist, title, kind) in enumerate(await cur.fetchall()):
                add(artist, weights.get(kind, 0))
                key = f"{artist} - {title}".lower()
                if kind == "skip":
                    skipped.add(key)
                if i < 40:
                    recent.add(key)
        async with self.conn.execute("SELECT performer FROM plays WHERE user_id=? AND created>=? LIMIT 2000",
                                     (user_id, since)) as cur:
            for (performer,) in await cur.fetchall():
                add(performer, 1)
        for like in await self.get_likes(user_id, limit=200):
            artist, _, title = like["title"].partition(" - ")
            if title:
                add(artist, 4)
        best = sorted(((names[k], v) for k, v in score.items() if v > 0), key=lambda x: -x[1])
        return {"artists": best, "skipped": skipped, "recent": recent}

    async def year_stats(self, user_id: int, year: int) -> dict:
        import datetime as _dt
        start = int(_dt.datetime(year, 1, 1).timestamp())
        end = int(_dt.datetime(year + 1, 1, 1).timestamp())
        args = (user_id, start, end)
        total = await self._scalar("SELECT COUNT(*) FROM plays WHERE user_id=? AND created>=? AND created<?", *args)
        days = await self._scalar(
            "SELECT COUNT(DISTINCT date(created, 'unixepoch')) FROM plays WHERE user_id=? AND created>=? AND created<?",
            *args)
        async with self.conn.execute(
            "SELECT performer, COUNT(*) c FROM plays WHERE user_id=? AND created>=? AND created<? AND performer<>'' "
            "GROUP BY lower(performer) ORDER BY c DESC, max(created) DESC LIMIT 5", args) as cur:
            artists = [(r[0], r[1]) for r in await cur.fetchall()]
        async with self.conn.execute(
            "SELECT title, performer, COUNT(*) c FROM plays WHERE user_id=? AND created>=? AND created<? "
            "GROUP BY lower(performer), lower(title) ORDER BY c DESC, max(created) DESC LIMIT 5", args) as cur:
            songs = [(r[0], r[1], r[2]) for r in await cur.fetchall()]
        return {"total": total, "days": days, "artists": artists, "songs": songs}

    # artist subscriptions: new-release alerts
    async def toggle_follow(self, user_id: int, artist_id: str, name: str) -> bool:
        cur = await self.conn.execute("DELETE FROM follows WHERE user_id=? AND artist_id=?", (user_id, artist_id))
        if not cur.rowcount:
            await self.conn.execute("INSERT INTO follows(user_id, artist_id, artist_name, created) VALUES(?,?,?,?)",
                                    (user_id, artist_id, name, int(time.time())))
        await self.conn.commit()
        return not cur.rowcount

    async def follows_of(self, user_id: int) -> list[tuple[str, str]]:
        async with self.conn.execute("SELECT artist_id, artist_name FROM follows WHERE user_id=? ORDER BY created",
                                     (user_id,)) as cur:
            return [(r[0], r[1]) for r in await cur.fetchall()]

    async def followed_artists(self) -> list[tuple[str, str]]:
        async with self.conn.execute("SELECT artist_id, max(artist_name) FROM follows GROUP BY artist_id") as cur:
            return [(r[0], r[1]) for r in await cur.fetchall()]

    async def followers(self, artist_id: str) -> list[int]:
        async with self.conn.execute("SELECT user_id FROM follows WHERE artist_id=?", (artist_id,)) as cur:
            return [r[0] for r in await cur.fetchall()]

    async def artist_state(self, artist_id: str) -> tuple[str | None, str | None]:
        async with self.conn.execute("SELECT release_id, release_title FROM artist_state WHERE artist_id=?",
                                     (artist_id,)) as cur:
            row = await cur.fetchone()
        return (row[0], row[1]) if row else (None, None)

    async def set_artist_state(self, artist_id: str, release_id: str, title: str) -> None:
        await self.conn.execute(
            "INSERT INTO artist_state(artist_id, release_id, release_title, checked) VALUES(?,?,?,?) "
            "ON CONFLICT(artist_id) DO UPDATE SET release_id=excluded.release_id, "
            "release_title=excluded.release_title, checked=excluded.checked",
            (artist_id, release_id, title, int(time.time())))
        await self.conn.commit()

    # playlists
    async def create_playlist(self, owner: int, name: str) -> dict:
        import secrets
        code = secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")
        cur = await self.conn.execute("INSERT INTO playlists(owner, name, code, created) VALUES(?,?,?,?)",
                                      (owner, name[:60], code, int(time.time())))
        await self.conn.commit()
        return {"id": cur.lastrowid, "owner": owner, "name": name[:60], "code": code}

    async def playlists_of(self, owner: int) -> list[dict]:
        async with self.conn.execute(
                "SELECT p.id, p.name, p.code, (SELECT COUNT(*) FROM playlist_items i WHERE i.playlist_id=p.id) "
                "FROM playlists p WHERE owner=? ORDER BY p.created DESC", (owner,)) as cur:
            return [{"id": r[0], "name": r[1], "code": r[2], "count": r[3], "owner": owner}
                    for r in await cur.fetchall()]

    async def get_playlist(self, pid: int | None = None, code: str | None = None) -> dict | None:
        sql, arg = ("id=?", pid) if pid is not None else ("code=?", code)
        async with self.conn.execute(f"SELECT id, owner, name, code FROM playlists WHERE {sql}", (arg,)) as cur:
            r = await cur.fetchone()
        return {"id": r[0], "owner": r[1], "name": r[2], "code": r[3]} if r else None

    async def playlist_items(self, pid: int) -> list[dict]:
        async with self.conn.execute(
                "SELECT file_id, title, duration FROM playlist_items WHERE playlist_id=? ORDER BY created", (pid,)) as cur:
            return [{"id": f"fid:{r[0]}", "title": r[1] or "♪", "duration": r[2] or 0} for r in await cur.fetchall()]

    async def add_to_playlist(self, pid: int, unique_id: str, file_id: str, title: str, duration: int) -> bool:
        cur = await self.conn.execute(
            "INSERT OR IGNORE INTO playlist_items(playlist_id, unique_id, file_id, title, duration, created) "
            "VALUES(?,?,?,?,?,?)", (pid, unique_id, file_id, title, duration, int(time.time())))
        await self.conn.commit()
        return bool(cur.rowcount)

    async def delete_playlist(self, pid: int, owner: int) -> bool:
        cur = await self.conn.execute("DELETE FROM playlists WHERE id=? AND owner=?", (pid, owner))
        if cur.rowcount:
            await self.conn.execute("DELETE FROM playlist_items WHERE playlist_id=?", (pid,))
        await self.conn.commit()
        return bool(cur.rowcount)
