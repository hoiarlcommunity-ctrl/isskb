from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from database.connection import get_db_conn
from websocket.manager import manager
import asyncpg

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

ALLOWED_STATUSES = {"open", "in_progress", "closed"}

STATUS_LABELS = {
    "open":        "Открыт",
    "in_progress": "В работе",
    "closed":      "Закрыт",
}


class IncidentStatusUpdate(BaseModel):
    status: str
    comment: str = ""
    author: str = "Оператор"


class CommentCreate(BaseModel):
    text: str
    author: str = "Оператор"


@router.get("")
async def list_incidents(
    status:   str | None = Query(None),
    severity: str | None = Query(None),
    limit:    int        = Query(50, le=200),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f"i.status = ${idx}")
        params.append(status)
        idx += 1
    if severity:
        conditions.append(f"i.severity = ${idx}")
        params.append(severity)
        idx += 1

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    rows = await conn.fetch(f"""
        SELECT
            i.id::text, i.severity, i.type, i.title, i.description,
            i.status, i.created_at, i.acknowledged_at, i.resolved_at, i.updated_at,
            d.id AS device_id,
            d.name AS device_name, d.serial_number,
            dc.icon AS device_icon, dc.code AS category_code
        FROM incidents i
        LEFT JOIN devices d            ON d.id  = i.device_id
        LEFT JOIN device_categories dc ON dc.id = d.category_id
        {where}
        ORDER BY
            CASE i.status
                WHEN 'open'        THEN 0
                WHEN 'in_progress' THEN 1
                ELSE 2
            END,
            CASE i.severity
                WHEN 'critical' THEN 0
                WHEN 'high'     THEN 1
                WHEN 'medium'   THEN 2
                WHEN 'low'      THEN 3
                ELSE 4
            END,
            i.created_at DESC
        LIMIT ${idx}
    """, *params)

    return [_ser(r) for r in rows]


@router.patch("/{incident_id}/status")
async def update_status(
    incident_id: str,
    body: IncidentStatusUpdate,
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    if body.status not in ALLOWED_STATUSES:
        raise HTTPException(400, f"Допустимые статусы: {sorted(ALLOWED_STATUSES)}")

    now = datetime.now(timezone.utc)
    res_at = now if body.status == "closed" else None

    row = await conn.fetchrow("""
        UPDATE incidents
        SET status      = $1,
            resolved_at = COALESCE(resolved_at, $2),
            updated_at  = $3
        WHERE id = $4::uuid
        RETURNING id::text, status, resolved_at, updated_at
    """, body.status, res_at, now, incident_id)

    if not row:
        raise HTTPException(404, "Инцидент не найден")

    # Auto-add comment on status change
    label = STATUS_LABELS.get(body.status, body.status)
    text  = f"Статус изменён на «{label}»"
    if body.comment.strip():
        text += f". {body.comment.strip()}"

    await conn.execute(
        """INSERT INTO incident_comments (incident_id, author, text, new_status)
           VALUES ($1::uuid, $2, $3, $4)""",
        incident_id, body.author, text, body.status,
    )

    result = _ser(row)
    await manager.broadcast("incident_updated", result)
    return result


@router.get("/{incident_id}/comments")
async def get_comments(
    incident_id: str,
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    rows = await conn.fetch("""
        SELECT id, author, text, new_status, created_at
        FROM incident_comments
        WHERE incident_id = $1::uuid
        ORDER BY created_at ASC
    """, incident_id)
    return [_ser_comment(r) for r in rows]


@router.post("/{incident_id}/comments")
async def add_comment(
    incident_id: str,
    body: CommentCreate,
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    exists = await conn.fetchval(
        "SELECT 1 FROM incidents WHERE id = $1::uuid", incident_id
    )
    if not exists:
        raise HTTPException(404, "Инцидент не найден")

    row = await conn.fetchrow(
        """INSERT INTO incident_comments (incident_id, author, text)
           VALUES ($1::uuid, $2, $3)
           RETURNING id, author, text, new_status, created_at""",
        incident_id, body.author, body.text,
    )
    return _ser_comment(row)


# ── Legacy PATCH (keep backward compat) ──────────────────────────────────────
class IncidentUpdate(BaseModel):
    status: str
    operator_id: int | None = None


@router.patch("/{incident_id}")
async def update_incident(
    incident_id: str,
    body: IncidentUpdate,
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    # Map old statuses to new
    status_map = {
        "acknowledged": "in_progress",
        "resolved":     "closed",
        "false_alarm":  "closed",
    }
    new_status = status_map.get(body.status, body.status)
    if new_status not in ALLOWED_STATUSES:
        new_status = "open"

    now = datetime.now(timezone.utc)
    res_at = now if new_status == "closed" else None

    row = await conn.fetchrow("""
        UPDATE incidents
        SET status      = $1,
            resolved_at = COALESCE(resolved_at, $2),
            updated_at  = $3
        WHERE id = $4::uuid
        RETURNING id::text, status, resolved_at, updated_at
    """, new_status, res_at, now, incident_id)

    if not row:
        raise HTTPException(404, "Incident not found")
    return _ser(row)


def _ser(r) -> dict:
    d = dict(r)
    for k in ("created_at", "acknowledged_at", "resolved_at", "updated_at"):
        if d.get(k) is not None and hasattr(d[k], "isoformat"):
            d[k] = d[k].isoformat()
    return d


def _ser_comment(r) -> dict:
    d = dict(r)
    if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    return d
