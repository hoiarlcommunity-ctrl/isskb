"""
External integration API.

POST /api/external/devices  — receives device data from external system (object or array),
                              applies field_map from active source config,
                              syncs to main DB, broadcasts WS notification.
GET  /api/external/status   — returns last heartbeat status.
GET  /api/external/ping     — triggers immediate connectivity check.
"""
import json
import os
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from database.connection import get_db_conn
from services.sync import sync_to_main
from services.heartbeat import get_status as heartbeat_status, _ping
from websocket.manager import manager

router = APIRouter(prefix="/api/external", tags=["external"])

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "settings.json"
_EXTERNAL_TOKEN = os.getenv("SENTINEL_EXTERNAL_TOKEN", "").strip()


def _load_active_field_map() -> dict | None:
    """Return field_map of the first active source from settings.json, or None."""
    try:
        if _CONFIG_FILE.exists():
            cfg = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            for src in cfg.get("ext_sources", []):
                if src.get("is_active", True):
                    fm = src.get("field_map")
                    if fm and isinstance(fm, dict):
                        return fm
    except Exception:
        pass
    return None


@router.post("/devices")
async def receive_devices(
    request: Request,
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    """
    Accepts both a single object and an array of device records.
    Field names are remapped according to the active source's field_map from settings.

    Single:  {"name": "КАМ-001", "online": true, "status": "active", "lat": 55.75, "lon": 37.61}
    Array:   [{"name": "КАМ-001", ...}, {"name": "КАМ-002", ...}]

    Custom fields (e.g. battery_level, signal_strength, temperature) are also accepted
    and stored in device_states.extra_state / device_states columns.
    """
    if _EXTERNAL_TOKEN:
        received_token = request.headers.get("x-api-key", "").strip()
        if received_token != _EXTERNAL_TOKEN:
            raise HTTPException(401, {"error": "Неверный или отсутствующий X-API-Key"})

    raw = await request.body()
    content_type = request.headers.get("content-type", "НЕ УКАЗАН")
    print(f"[EXT] POST /devices | content-type={content_type} | len={len(raw)}")

    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(400, {
            "error": "Невалидный JSON",
            "detail": str(e),
            "content_type": content_type,
            "received_raw": raw.decode("utf-8", errors="replace")[:500],
        })

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list) or len(data) == 0:
        raise HTTPException(400, {
            "error": "Ожидался объект или непустой массив устройств",
            "received": str(data)[:200],
        })

    # Validate that each item is a dict (basic check)
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise HTTPException(422, {"error": f"Элемент [{i}] должен быть объектом"})

    field_map = _load_active_field_map()
    if field_map:
        print(f"[EXT] Applying field_map: {field_map}")

    try:
        result = await sync_to_main(conn, data, field_map=field_map)
    except Exception as e:
        print(f"[EXT] sync error: {e}")
        raise HTTPException(500, {"error": f"Ошибка синхронизации: {str(e)[:200]}"})

    await manager.broadcast("devices_updated", result)
    print(f"[EXT] sync result: {result}")

    return {**result, "received": data}


@router.get("/status")
async def external_status():
    """Returns last heartbeat check result."""
    return heartbeat_status()


@router.get("/ping")
async def manual_ping():
    """Triggers an immediate connectivity check and broadcasts result via WebSocket."""
    ok, error = await _ping()
    from datetime import datetime, timezone
    _state = {"ok": ok, "checked_at": datetime.now(timezone.utc).isoformat(), "error": error}
    await manager.broadcast("ext_heartbeat", _state)
    return _state
