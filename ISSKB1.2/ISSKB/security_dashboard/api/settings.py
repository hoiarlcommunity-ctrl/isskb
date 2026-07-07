"""
Settings API — external data sources configuration. Admin only.

GET    /api/settings/sources            — list all
POST   /api/settings/sources            — create
PUT    /api/settings/sources/{id}       — update
DELETE /api/settings/sources/{id}       — delete
POST   /api/settings/sources/{id}/ping  — test connectivity
GET    /api/settings/buffer             — ext_devices stats
DELETE /api/settings/buffer             — clear ext_devices
"""
import json
from pathlib import Path
from typing import Optional

import httpx
import asyncpg
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from api.admin import require_admin
from database.connection import get_db_conn
from services import heartbeat as hb_module

router = APIRouter(prefix="/api/settings", tags=["settings"])

CONFIG_FILE = Path(__file__).parent.parent / "config" / "settings.json"
CONFIG_FILE.parent.mkdir(exist_ok=True)

_DEFAULT_FIELD_MAP = {
    "name": "name", "online": "online",
    "status": "status", "lat": "lat", "lon": "lon",
}

_DEFAULT_CONFIG = {
    "ext_sources": [
        {
            "id": 1,
            "name": "Основной сервер ПСО",
            "description": "Сервер данных ПСО",
            "base_url": "http://10.26.205.80",
            "ping_path": "/time.php?komandos=run",
            "ping_ok_text": "ok",
            "is_active": True,
            "is_heartbeat": True,
            "timeout_s": 10,
            "field_map": _DEFAULT_FIELD_MAP.copy(),
        }
    ]
}


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        _save_config(_DEFAULT_CONFIG, notify=False)
        return _DEFAULT_CONFIG.copy()
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _DEFAULT_CONFIG.copy()


def _save_config(cfg: dict, notify: bool = True) -> None:
    CONFIG_FILE.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if notify:
        hb_module.reload_config(cfg.get("ext_sources", []))


class SourceBody(BaseModel):
    name: str
    description: Optional[str] = None
    base_url: str
    ping_path: Optional[str] = "/"
    ping_ok_text: Optional[str] = None
    is_active: bool = True
    is_heartbeat: bool = False
    timeout_s: int = 10
    field_map: Optional[dict] = None
    # Data polling (GET device list from external server)
    data_path: Optional[str] = None           # e.g. "/time.php?komandos=settings"
    response_format: str = "json"             # "json" or "php_print_r"
    poll_interval_s: int = 60                 # poll every N seconds


@router.get("/sources")
async def list_sources(user=Depends(require_admin)):
    return _load_config().get("ext_sources", [])


@router.post("/sources", status_code=201)
async def create_source(body: SourceBody, user=Depends(require_admin)):
    cfg = _load_config()
    sources = cfg.setdefault("ext_sources", [])
    new_id = max((s["id"] for s in sources), default=0) + 1
    src = body.model_dump()
    src["id"] = new_id
    if src["field_map"] is None:
        src["field_map"] = _DEFAULT_FIELD_MAP.copy()
    sources.append(src)
    _save_config(cfg)
    return src


@router.put("/sources/{src_id}")
async def update_source(src_id: int, body: SourceBody, user=Depends(require_admin)):
    cfg = _load_config()
    sources = cfg.get("ext_sources", [])
    idx = next((i for i, s in enumerate(sources) if s["id"] == src_id), None)
    if idx is None:
        raise HTTPException(404, "Источник не найден")
    updated = body.model_dump()
    updated["id"] = src_id
    if updated["field_map"] is None:
        updated["field_map"] = sources[idx].get("field_map", _DEFAULT_FIELD_MAP.copy())
    sources[idx] = updated
    cfg["ext_sources"] = sources
    _save_config(cfg)
    return updated


@router.delete("/sources/{src_id}")
async def delete_source(src_id: int, user=Depends(require_admin)):
    cfg = _load_config()
    sources = cfg.get("ext_sources", [])
    new_list = [s for s in sources if s["id"] != src_id]
    if len(new_list) == len(sources):
        raise HTTPException(404, "Источник не найден")
    cfg["ext_sources"] = new_list
    _save_config(cfg)
    return {"ok": True}


@router.post("/sources/{src_id}/ping")
async def ping_source(src_id: int, user=Depends(require_admin)):
    cfg = _load_config()
    src = next((s for s in cfg.get("ext_sources", []) if s["id"] == src_id), None)
    if not src:
        raise HTTPException(404, "Источник не найден")

    base    = src["base_url"].rstrip("/")
    path    = (src.get("ping_path") or "").lstrip("/")
    url     = f"{base}/{path}" if path else base
    ok_text = (src.get("ping_ok_text") or "").strip().lower()
    timeout = int(src.get("timeout_s", 10))

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
        if r.status_code == 200:
            if ok_text and r.text.strip().lower() != ok_text:
                return {
                    "ok": False, "status_code": r.status_code,
                    "error": f"Ожидался ответ '{ok_text}', получено: '{r.text[:80]}'",
                }
            return {"ok": True, "status_code": r.status_code, "response": r.text[:100]}
        return {"ok": False, "status_code": r.status_code, "error": f"HTTP {r.status_code}"}
    except httpx.TimeoutException:
        return {"ok": False, "error": "Таймаут соединения"}
    except httpx.ConnectError as e:
        return {"ok": False, "error": f"Нет соединения: {str(e)[:80]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


@router.get("/buffer")
async def buffer_stats(
    conn: asyncpg.Connection = Depends(get_db_conn),
    user=Depends(require_admin),
):
    row = await conn.fetchrow("""
        SELECT
            COUNT(*)                               AS total,
            COUNT(*) FILTER (WHERE online = TRUE)  AS online_count,
            MAX(received_at)                       AS last_received,
            MIN(received_at)                       AS first_received
        FROM ext_devices
    """)
    return {
        "total":          row["total"],
        "online":         row["online_count"],
        "last_received":  row["last_received"].isoformat()  if row["last_received"]  else None,
        "first_received": row["first_received"].isoformat() if row["first_received"] else None,
    }


@router.delete("/buffer")
async def clear_buffer(
    conn: asyncpg.Connection = Depends(get_db_conn),
    user=Depends(require_admin),
):
    await conn.execute("DELETE FROM ext_devices")
    return {"ok": True}
