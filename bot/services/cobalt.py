"""YouTube (and others) through public cobalt instances (https://github.com/imputnet/cobalt).

A cobalt server fetches the video from YouTube itself and streams it to us, so it works
even when YouTube blocks our server IP. No account, no cookies. Instances without
authentication come from the public list at instances.cobalt.best (cached for an hour);
COBALT_INSTANCES in .env (comma separated API URLs) puts your own first.
"""
import json
import logging
import os
import time

from .mp3sites import http_get

log = logging.getLogger(__name__)

LIST_URL = "https://instances.cobalt.best/api/instances.json"
LIST_TTL = 3600
MAX_INSTANCES = 6
DOWN_PAUSE = 10 * 60
MIN_BYTES = 20 * 1024

_cache: dict = {"at": 0.0, "list": []}
_good: list[str] = []
_down_until = 0.0
last_error = ""


def available() -> bool:
    return _down_until <= time.time()


def reset_pause() -> None:
    global _down_until
    _down_until = 0.0


def _norm(api: str) -> str:
    api = api.strip().rstrip("/")
    return api if api.startswith("http") else f"https://{api}"


def parse_list(data) -> list[str]:
    """Public instances that are online, need no auth and can do YouTube, best first."""
    items = data if isinstance(data, list) else (data or {}).get("instances") or []
    out: list[tuple[float, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        api = it.get("api") or it.get("api_url") or it.get("url")
        if not api or it.get("online") is False:
            continue
        info = it.get("info") if isinstance(it.get("info"), dict) else {}
        if it.get("auth") or info.get("auth") or it.get("turnstile") or info.get("turnstileSitekey"):
            continue
        services = it.get("services") if isinstance(it.get("services"), dict) else {}
        if services and not (services.get("youtube") is True or services.get("youtube") == "true"):
            continue
        out.append((float(it.get("score") or 0), _norm(api)))
    return [api for _, api in sorted(out, key=lambda x: x[0], reverse=True)]


def instances() -> list[str]:
    env = [_norm(x) for x in os.getenv("COBALT_INSTANCES", "").split(",") if x.strip()]
    if not (time.time() - _cache["at"] < LIST_TTL and _cache["list"]):
        try:
            found = parse_list(json.loads(http_get(LIST_URL, timeout=10)))
            if found:
                _cache.update(at=time.time(), list=found)
        except Exception as e:  # noqa: BLE001
            log.info("cobalt list unavailable: %s", str(e)[:120])
    out: list[str] = []
    for api in env + _good + _cache["list"]:
        if api not in out:
            out.append(api)
    return out[:MAX_INSTANCES + len(env)]


def _request(api: str, body: dict) -> dict:
    raw = http_get(api + "/", timeout=30, data=json.dumps(body).encode(),
                   headers={"Accept": "application/json", "Content-Type": "application/json"})
    return json.loads(raw)


def fetch(url: str, audio: bool, max_height: int = 1080) -> list[tuple[bytes, str]]:
    """Ask instances until one returns the media. Returns [(bytes, filename), ...]."""
    global _down_until, last_error
    if not available():
        raise RuntimeError(f"cobalt paused after recent failures ({last_error[:120]})")
    body = {"url": url, "filenameStyle": "basic"}
    if audio:
        body |= {"downloadMode": "audio", "audioFormat": "mp3", "audioBitrate": "320"}
    else:
        body |= {"downloadMode": "auto", "videoQuality": str(max_height), "youtubeVideoCodec": "h264"}
    errors = []
    for api in instances():
        try:
            res = _request(api, body)
            status = res.get("status")
            if status in ("tunnel", "redirect", "stream"):
                links = [(res["url"], res.get("filename") or "")]
            elif status == "picker":
                links = [(p["url"], "") for p in res.get("picker") or [] if p.get("url")][:10]
            else:
                err = res.get("error") or {}
                raise RuntimeError(err.get("code") if isinstance(err, dict) else str(err) or status)
            files = []
            for link, name in links:
                data = http_get(link, timeout=300)
                if len(data) < MIN_BYTES:
                    raise RuntimeError(f"empty file ({len(data)} bytes)")
                files.append((data, name))
            if api in _good:
                _good.remove(api)
            _good.insert(0, api)
            del _good[5:]
            log.info("cobalt OK via %s for %s", api, url)
            return files
        except Exception as e:  # noqa: BLE001
            errors.append(f"{api}: {str(e)[:100]}")
            if api in _good:
                _good.remove(api)
    last_error = " | ".join(errors[-3:]) or "no public cobalt instances known"
    _down_until = time.time() + DOWN_PAUSE
    raise RuntimeError(last_error)
