"""
Device data poller — periodically fetches device lists from configured external sources.

For each active source that has `data_path` set:
  - GETs {base_url}/{data_path} at `poll_interval_s` interval
  - Parses response (JSON or PHP print_r)
  - Downloads device icons locally
  - Applies field_map remapping
  - Calls sync_to_main → updates main DB and broadcasts WS events
"""

import asyncio
import json
import re
import time
from pathlib import Path

import httpx

from services.php_parser import parse_php_printout
from services.sync import sync_to_main, _remap
import services.syslog as syslog

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "settings.json"
_ICONS_DIR   = Path(__file__).parent.parent / "static" / "icons" / "devices"
_last_poll: dict[int, float] = {}  # source_id → last poll timestamp


# ── Config loader ─────────────────────────────────────────────────────────────

def _load_sources() -> list[dict]:
    try:
        if _CONFIG_FILE.exists():
            cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            return cfg.get("ext_sources", [])
    except Exception:
        pass
    return []


# ── Icon downloader ───────────────────────────────────────────────────────────

async def _download_icon(base_url: str, img_path: str, device_name: str) -> str | None:
    """Download icon from external server; return local static path or None."""
    if not img_path:
        return None

    url = f"{base_url.rstrip('/')}/{img_path.lstrip('/')}"
    safe  = re.sub(r"[^\w\-]", "_", device_name)[:40]
    ext   = Path(img_path.split("?")[0]).suffix.lower() or ".png"
    fname = f"ext_{safe}{ext}"
    dest  = _ICONS_DIR / fname

    # Re-use existing icon if downloaded within last 24 h
    if dest.exists() and (time.time() - dest.stat().st_mtime) < 86400:
        return f"/static/icons/devices/{fname}"

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200 and r.content:
            _ICONS_DIR.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return f"/static/icons/devices/{fname}"
    except Exception as e:
        print(f"[POLLER] Icon download failed ({url}): {e}")
    return None


# ── Single source poll ────────────────────────────────────────────────────────

async def _poll_source(source: dict) -> None:
    from database.connection import DSN
    from websocket.manager import manager
    import asyncpg

    src_id   = source["id"]
    base_url = source["base_url"].rstrip("/")
    data_path = (source.get("data_path") or "").strip().lstrip("/")
    url       = f"{base_url}/{data_path}" if data_path else None

    if not url:
        return

    fmt       = source.get("response_format", "json")
    field_map = source.get("field_map") or {}
    timeout   = int(source.get("timeout_s", 10))

    syslog.add("info", "poller", f"Опрос источника #{src_id}", f"GET {url} (формат: {fmt})")
    print(f"[POLLER] Polling source {src_id}: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url)

        if r.status_code != 200:
            msg = f"HTTP {r.status_code} от источника #{src_id}"
            syslog.add("warn", "poller", msg, url)
            print(f"[POLLER] Source {src_id}: HTTP {r.status_code}")
            return

        syslog.add("debug", "poller", f"Ответ получен: HTTP {r.status_code}, {len(r.content)} байт", url)

        # Decode — try UTF-8 first, fall back to cp1251
        try:
            text = r.content.decode("utf-8")
        except UnicodeDecodeError:
            text = r.content.decode("cp1251", errors="replace")

        # Parse
        if fmt == "php_print_r":
            raw_records = parse_php_printout(text)
        else:
            try:
                data = json.loads(text)
                raw_records = data if isinstance(data, list) else [data]
            except Exception:
                syslog.add("error", "poller", f"Ошибка парсинга JSON от источника #{src_id}", text[:200])
                print(f"[POLLER] Source {src_id}: JSON parse failed")
                return

        syslog.add("info", "poller", f"Разобрано {len(raw_records)} устройств от источника #{src_id}", url)
        print(f"[POLLER] Source {src_id}: {len(raw_records)} records parsed")
        if not raw_records:
            return

        # Apply field_map, handle icons, build final records
        records: list[dict] = []
        for raw in raw_records:
            rec = _remap(raw, field_map) if field_map else dict(raw)

            # Handle icon download (system field: icon_url → local icon_path)
            icon_url = rec.pop("icon_url", None) or raw.get("img")
            if icon_url:
                device_name = str(rec.get("name") or rec.get("external_key") or "device")
                local_path  = await _download_icon(base_url, str(icon_url), device_name)
                if local_path:
                    rec["icon_path"] = local_path
                    syslog.add("debug", "poller", f"Иконка загружена: {device_name}", local_path)

            records.append(rec)

        # Sync to main DB
        conn = await asyncpg.connect(DSN)
        try:
            result = await sync_to_main(conn, records)
        finally:
            await conn.close()

        await manager.broadcast("devices_updated", result)
        syslog.add("info", "sync", f"Синхронизировано с БД: создано {result.get('created',0)}, обновлено {result.get('updated',0)}", f"источник #{src_id}")
        print(f"[POLLER] Source {src_id} synced: {result}")

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        syslog.add("error", "poller", f"Ошибка опроса источника #{src_id}: {exc}", url)
        print(f"[POLLER] Source {src_id} error: {exc}")


# ── Main loop ─────────────────────────────────────────────────────────────────

async def poller_loop() -> None:
    """Background task: polls each active source on its configured interval."""
    print("[POLLER] Device data poller starting...")
    await asyncio.sleep(12)   # let server fully start before first poll

    while True:
        sources = _load_sources()
        now     = time.time()

        for src in sources:
            src_id   = src.get("id")
            interval = int(src.get("poll_interval_s", 60))
            last     = _last_poll.get(src_id, 0)

            if (
                src.get("is_active")
                and src.get("data_path")
                and (now - last) >= interval
            ):
                _last_poll[src_id] = now
                asyncio.create_task(_poll_source(src))

        await asyncio.sleep(5)   # check every 5 s for due polls
