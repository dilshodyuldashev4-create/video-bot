import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    admin_ids: frozenset[int] = field(
        default_factory=lambda: frozenset(
            int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
        )
    )
    api_url: str = field(default_factory=lambda: os.getenv("TELEGRAM_API_URL", "").rstrip("/"))
    cookies_file: str = field(default_factory=lambda: os.getenv("COOKIES_FILE", ""))
    # socks5/http proxy used when a site blocks the server IP (docker-compose: Cloudflare WARP)
    proxy: str = field(default_factory=lambda: os.getenv("PROXY_URL", "").strip())
    # bgutil PO-token provider for YouTube (docker-compose: pot-provider service)
    pot_url: str = field(default_factory=lambda: os.getenv("POT_PROVIDER_URL", "").strip().rstrip("/"))
    max_parallel: int = field(default_factory=lambda: _int("MAX_PARALLEL_DOWNLOADS", 4))
    max_height: int = field(default_factory=lambda: _int("MAX_VIDEO_HEIGHT", 1080))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "./data")).resolve())

    @property
    def local_api(self) -> bool:
        return bool(self.api_url)

    @property
    def upload_limit(self) -> int:
        """Max file size the bot can send (bytes)."""
        return (2000 if self.local_api else 49) * 1024 * 1024

    @property
    def download_limit(self) -> int:
        """Max size of a user file the bot can fetch from Telegram (bytes)."""
        return (2000 if self.local_api else 20) * 1024 * 1024

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bot.sqlite3"

    @property
    def cookies(self) -> str | None:
        return self.cookies_file if self.cookies_file and Path(self.cookies_file).is_file() else None


config = Config()
