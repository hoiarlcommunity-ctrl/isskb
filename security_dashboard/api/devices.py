import json
import shutil
import decimal
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from database.connection import get_db_conn
from websocket.manager import manager
import asyncpg


class _Enc(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

router = APIRouter(prefix="/api/devices", tags=["devices"])

ICONS_DIR = Path(__file__).parent.parent / "static" / "icons" / "devices"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


class DevicePatch(BaseModel):
    operational_mode: Optional[str] = None
    responsible_person: Optional[str] = None
    maintenance_comment: Optional[str] = None


_DEVICE_SELECT = """
    SELECT
        d.id, d.category_id, d.name, d.serial_number, d.model, d.manufacturer,
        d.ip_address, d.firmware_version, d.is_mobile, d.description,
        d.responsible_person, d.installation_date, d.created_at, d.icon_path,
        d.external_key, d.port, d.priority, d.device_type,
        d.detection_ranges  AS detection_ranges,
        dc.code      AS category_code,
        dc.name      AS category_name,
        dc.icon      AS category_icon,
        dc.icon_path AS category_icon_path,
        dc.color     AS category_color,
        z.name   AS zone_name,
        z.code   AS zone_code,
        z.color  AS zone_color,
        dp.latitude, dp.longitude, dp.heading, dp.speed,
        ds.online_status, ds.operational_mode, ds.battery_level,
        ds.signal_strength, ds.last_heartbeat, ds.last_seen,
        ds.error_code, ds.extra_state AS extra_state
    FROM devices d
    JOIN device_categories dc ON dc.id = d.category_id
    LEFT JOIN zones z         ON z.id  = d.zone_id
    LEFT JOIN device_positions dp
           ON dp.device_id = d.id AND dp.is_current = TRUE
    LEFT JOIN device_states ds ON ds.device_id = d.id
"""


@router.get("")
async def list_devices(conn: asyncpg.Connection = Depends(get_db_conn)):
    rows = await conn.fetch(_DEVICE_SELECT + " ORDER BY dc.code, d.name")
    result = [_serialize(r) for r in rows]
    return Response(content=json.dumps(result, cls=_Enc, ensure_ascii=False), media_type="application/json")


@router.get("/{device_id}")
async def get_device(device_id: int, conn: asyncpg.Connection = Depends(get_db_conn)):
    row = await conn.fetchrow(_DEVICE_SELECT + " WHERE d.id = $1", device_id)

    if not row:
        raise HTTPException(404, "Device not found")

    device = _serialize(row)

    # Recent metrics (last 10 per key)
    metrics_rows = await conn.fetch("""
        SELECT metric_key, metric_value, unit, recorded_at
        FROM device_metrics
        WHERE device_id = $1
        ORDER BY recorded_at DESC
        LIMIT 50
    """, device_id)

    metrics: dict = {}
    for m in metrics_rows:
        key = m["metric_key"]
        if key not in metrics:
            metrics[key] = []
        if len(metrics[key]) < 10:
            metrics[key].append({
                "value": float(m["metric_value"]) if m["metric_value"] is not None else None,
                "unit":  m["unit"],
                "ts":    m["recorded_at"].isoformat() if m["recorded_at"] else None,
            })

    device["metrics"] = metrics
    return Response(content=json.dumps(device, cls=_Enc, ensure_ascii=False), media_type="application/json")


@router.patch("/{device_id}")
async def patch_device(
    device_id: int,
    body: DevicePatch,
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    exists = await conn.fetchval("SELECT 1 FROM devices WHERE id=$1", device_id)
    if not exists:
        raise HTTPException(404, "Устройство не найдено")

    if body.responsible_person is not None:
        await conn.execute(
            "UPDATE devices SET responsible_person=$1, updated_at=NOW() WHERE id=$2",
            body.responsible_person, device_id,
        )

    if body.operational_mode is not None:
        allowed_modes = {"active", "idle", "alarm", "warning", "maintenance", "patrol", "offline"}
        if body.operational_mode not in allowed_modes:
            raise HTTPException(400, f"Допустимые режимы: {sorted(allowed_modes)}")
        await conn.execute(
            "UPDATE device_states SET operational_mode=$1, updated_at=NOW() WHERE device_id=$2",
            body.operational_mode, device_id,
        )
        # Auto-create incident when entering maintenance
        if body.operational_mode == "maintenance":
            comment = body.maintenance_comment or "Устройство переведено в режим ТО оператором"
            dev_name = await conn.fetchval("SELECT name FROM devices WHERE id=$1", device_id)
            inc = await conn.fetchrow(
                """INSERT INTO incidents (device_id, severity, type, title, description, status, created_at, updated_at)
                   VALUES ($1,'medium','maintenance',$2,$3,'in_progress',NOW(),NOW())
                   RETURNING id::text""",
                device_id,
                f"ТО — {dev_name}",
                comment,
            )
            await conn.execute(
                """INSERT INTO incident_comments (incident_id, author, text, new_status)
                   VALUES ($1::uuid,'Оператор',$2,'in_progress')""",
                inc["id"], f"Устройство переведено в режим ТО. {comment}",
            )

    # Return updated device
    row = await conn.fetchrow(_DEVICE_SELECT + " WHERE d.id = $1", device_id)
    result = _serialize(row)
    await manager.broadcast("device_updated", result)
    return Response(
        content=json.dumps(result, cls=_Enc, ensure_ascii=False),
        media_type="application/json",
    )


@router.post("/{device_id}/icon")
async def upload_device_icon(
    device_id: int,
    file: UploadFile = File(...),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    ext = Path(file.filename or "icon.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Недопустимый формат. Разрешены: {', '.join(ALLOWED_EXTS)}")

    dest = ICONS_DIR / f"{device_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    icon_path = f"/static/icons/devices/{device_id}{ext}"
    await conn.execute("UPDATE devices SET icon_path=$1 WHERE id=$2", icon_path, device_id)
    return {"icon_path": icon_path}


def _serialize(row) -> dict:
    d = dict(row)
    for k in ("created_at", "installation_date", "last_heartbeat", "last_seen"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat() if hasattr(d[k], "isoformat") else str(d[k])
    for k, default in (("detection_ranges", []), ("extra_state", {})):
        val = d.get(k)
        if val is None:
            d[k] = default
        elif isinstance(val, str):
            try:
                d[k] = json.loads(val)
            except Exception:
                d[k] = default
        elif isinstance(val, (list, dict)):
            pass  # already parsed by asyncpg codec
        # else: leave as-is (shouldn't happen)
    return d
