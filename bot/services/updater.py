"""Keeps yt-dlp fresh: YouTube changes every few weeks and old versions stop downloading.

start.sh updates it when the container starts; this task checks once a day and, when a new
version was installed, exits so Docker restarts the bot with it (restart: unless-stopped).
"""
import asyncio
import importlib.metadata
import logging
import os
import subprocess
import sys

log = logging.getLogger(__name__)

PACKAGES = ["yt-dlp[default]", "bgutil-ytdlp-pot-provider"]
EVERY = 24 * 3600


def installed() -> str:
    try:
        return importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        return ""


def upgrade_sync() -> str:
    """pip install -U; returns the yt-dlp version installed afterwards (from a fresh process)."""
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "-q", "-U", "--pre", *PACKAGES],
                   check=True, timeout=300, capture_output=True)
    out = subprocess.run([sys.executable, "-c", "import importlib.metadata as m; print(m.version('yt-dlp'))"],
                         check=True, timeout=60, capture_output=True, text=True)
    return out.stdout.strip()


async def run(busy=lambda: False) -> None:
    if os.environ.get("YTDLP_AUTO_UPDATE", "1") == "0":
        return
    while True:
        await asyncio.sleep(EVERY)
        before = installed()
        try:
            after = await asyncio.to_thread(upgrade_sync)
        except Exception as e:  # noqa: BLE001
            log.warning("yt-dlp update failed: %s", str(e)[:200])
            continue
        if after and after != before:
            log.warning("yt-dlp updated %s -> %s, restarting to use it", before, after)
            for _ in range(60):  # let running downloads finish (up to 5 min)
                if not busy():
                    break
                await asyncio.sleep(5)
            os._exit(0)
        log.info("yt-dlp %s is the latest", before)
