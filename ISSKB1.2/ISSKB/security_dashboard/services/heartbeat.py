"""
Background heartbeat — pings external data server every 30 seconds.
URL is read from config/settings.json (source with is_heartbeat=True).
Falls back to the hardcoded default if no config file exists yet.
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone

import httpx
import services.syslog as syslog

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "settings.json"

# Runtime heartbeat target — updated by reload_config() and on startup
_heartbeat: dict = {
    "url":     "http://10.26.205.80/time.php?komandos=run",
    "ok_text": "ok",
    "timeout": 10,
}

INTERVAL_SECONDS = 30

_state: dict = {"ok": None, "checked_at": None, "error": None}

# Мониторинг внешнего сервера включён, пока в настройках есть активный
# heartbeat-источник. В автономном режиме (нет такого источника) — выключается,
# чтобы не слать ложную тревогу «нет связи».
_enabled: bool = True


def _parse_source(s: dict) -> dict:
    base = s["base_url"].rstrip("/")
    path = (s.get("ping_path") or "").lstrip("/")
    url  = f"{base}/{path}" if path else base
    return {
        "url":     url,
        "ok_text": (s.get("ping_ok_text") or "").strip().lower(),
        "timeout": int(s.get("timeout_s", 10)),
    }


def _load_from_file() -> None:
    global _enabled
    try:
        if _CONFIG_FILE.exists():
            cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            for s in cfg.get("ext_sources", []):
                if s.get("is_heartbeat") and s.get("is_active", True):
                    _heartbeat.update(_parse_source(s))
                    _enabled = True
                    return
            # Файл настроек есть, но активного heartbeat-источника нет →
            # автономный режим: мониторинг внешнего сервера отключён.
            _enabled = False
    except Exception:
        pass


def reload_config(sources: list) -> None:
    """Called by settings API when config changes."""
    global _enabled
    for s in sources:
        if s.get("is_heartbeat") and s.get("is_active", True):
            _heartbeat.update(_parse_source(s))
            _enabled = True
            return
    _enabled = False


async def heartbeat_loop() -> None:
    from websocket.manager import manager  # avoid circular import at module level

    _load_from_file()

    if not _enabled:
        syslog.add("info", "heartbeat",
                   "Мониторинг внешнего сервера отключён (нет активного источника)")

    while True:
        # Автономный режим: активного heartbeat-источника нет — не опрашиваем
        # и не шлём тревогу «нет связи». Цикл жив, чтобы reload_config мог
        # включить мониторинг без перезапуска сервера.
        if not _enabled:
            _state["ok"] = None
            await asyncio.sleep(INTERVAL_SECONDS)
            continue

        ok, error = await _ping()
        _state["ok"]         = ok
        _state["checked_at"] = datetime.now(timezone.utc).isoformat()
        _state["error"]      = error

        url = _heartbeat.get("url", "—")
        if ok:
            syslog.add("info", "heartbeat", f"Heartbeat OK → {url}")
        else:
            syslog.add("warn", "heartbeat", f"Heartbeat FAIL → {url}", error)

        await manager.broadcast("ext_heartbeat", {
            "ok":         ok,
            "checked_at": _state["checked_at"],
            "error":      error,
        })

        await asyncio.sleep(INTERVAL_SECONDS)


async def _ping() -> tuple[bool, str | None]:
    url     = _heartbeat["url"]
    ok_text = _heartbeat["ok_text"]
    timeout = _heartbeat["timeout"]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
        if r.status_code == 200:
            if ok_text and r.text.strip().lower() != ok_text:
                return False, f"Неожиданный ответ: {r.text[:80]}"
            return True, None
        return False, f"HTTP {r.status_code}"
    except httpx.TimeoutException:
        return False, "Таймаут соединения"
    except httpx.ConnectError:
        return False, "Нет соединения с сервером"
    except Exception as e:
        return False, str(e)[:120]


def get_status() -> dict:
    return dict(_state)
