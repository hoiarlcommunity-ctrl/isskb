"""Административный API — CRUD устройств, категорий, зон. Только роль admin."""
import shutil
from pathlib import Path
from typing import Optional, List, Any

from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field
from database.connection import get_db_conn
from api.admin import require_admin
import asyncpg

router = APIRouter(prefix="/api/admin", tags=["admin-devices"])

_STATIC = Path(__file__).parent.parent / "static"
DEVICE_ICONS_DIR = _STATIC / "icons" / "devices"
CAT_ICONS_DIR    = _STATIC / "icons" / "categories"
ALLOWED_IMG      = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

DEVICE_ICONS_DIR.mkdir(parents=True, exist_ok=True)
CAT_ICONS_DIR.mkdir(parents=True, exist_ok=True)


# ── Pydantic models ───────────────────────────────────────────────────────────

class DeviceCreate(BaseModel):
    name: str = Field(..., max_length=200)
    category_id: int
    zone_id: Optional[int] = None
    serial_number: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=200)
    ip_address: Optional[str] = Field(None, max_length=50)
    firmware_version: Optional[str] = Field(None, max_length=100)
    installation_date: Optional[str] = None
    is_mobile: bool = False
    description: Optional[str] = None
    responsible_person: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = None
    detection_ranges: Optional[List[Any]] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    category_id: Optional[int] = None
    zone_id: Optional[int] = None
    serial_number: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=200)
    ip_address: Optional[str] = Field(None, max_length=50)
    firmware_version: Optional[str] = Field(None, max_length=100)
    installation_date: Optional[str] = None
    is_mobile: Optional[bool] = None
    description: Optional[str] = None
    responsible_person: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = None
    detection_ranges: Optional[List[Any]] = None


class CategoryCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    icon: Optional[str] = Field("📦", max_length=10)
    color: Optional[str] = Field("#3b82f6", max_length=30)
    tab_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    icon: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, max_length=30)
    tab_id: Optional[int] = None


class ZoneCreate(BaseModel):
    name: str = Field(..., max_length=200)
    code: str = Field(..., max_length=50)
    color: Optional[str] = Field("#3b82f6", max_length=30)
    description: Optional[str] = None
    lat_center: Optional[float] = None
    lon_center: Optional[float] = None
    radius_m: Optional[int] = Field(200, ge=1)


class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    code: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=30)
    description: Optional[str] = None
    lat_center: Optional[float] = None
    lon_center: Optional[float] = None
    radius_m: Optional[int] = Field(None, ge=1)


# ── helper ────────────────────────────────────────────────────────────────────

def _build_update(body_dict: dict) -> tuple[list, list]:
    """Build SET clause components from a non-empty dict. Returns (clauses, params)."""
    clauses, params = [], []
    for i, (k, v) in enumerate(body_dict.items(), start=1):
        clauses.append(f"{k}=${i}")
        params.append(v)
    return clauses, params


# ── Devices ───────────────────────────────────────────────────────────────────

@router.post("/devices", status_code=201)
async def create_device(
    body: DeviceCreate,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    cat = await conn.fetchrow("SELECT id FROM device_categories WHERE id=$1", body.category_id)
    if not cat:
        raise HTTPException(400, f"Категория ID {body.category_id} не найдена")

    install_date = None
    if body.installation_date:
        from datetime import date
        try:
            install_date = date.fromisoformat(body.installation_date)
        except ValueError:
            raise HTTPException(400, "Неверный формат даты (ожидается YYYY-MM-DD)")

    row = await conn.fetchrow(
        """INSERT INTO devices (name, category_id, zone_id, serial_number, model,
                                manufacturer, ip_address, firmware_version,
                                installation_date, is_mobile, description,
                                responsible_person, location, notes, detection_ranges)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
           RETURNING *""",
        body.name, body.category_id, body.zone_id, body.serial_number,
        body.model, body.manufacturer, body.ip_address, body.firmware_version,
        install_date, body.is_mobile, body.description,
        body.responsible_person, body.location, body.notes, body.detection_ranges or [],
    )
    await conn.execute(
        """INSERT INTO device_states (device_id, online_status, operational_mode)
           VALUES ($1, FALSE, 'offline') ON CONFLICT (device_id) DO NOTHING""",
        row['id']
    )
    return dict(row)


@router.put("/devices/{device_id}")
async def update_device(
    device_id: int,
    body: DeviceUpdate,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    existing = await conn.fetchrow("SELECT id FROM devices WHERE id=$1", device_id)
    if not existing:
        raise HTTPException(404, "Устройство не найдено")

    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Нет данных для обновления")

    if 'installation_date' in updates and updates['installation_date']:
        from datetime import date
        try:
            updates['installation_date'] = date.fromisoformat(updates['installation_date'])
        except ValueError:
            raise HTTPException(400, "Неверный формат даты")

    clauses, params = _build_update(updates)
    clauses.append("updated_at=NOW()")
    params.append(device_id)

    row = await conn.fetchrow(
        f"UPDATE devices SET {', '.join(clauses)} WHERE id=${len(params)} RETURNING *",
        *params
    )
    return dict(row)


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: int,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    result = await conn.execute("DELETE FROM devices WHERE id=$1", device_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Устройство не найдено")


@router.post("/devices/{device_id}/icon")
async def upload_device_icon(
    device_id: int,
    request: Request,
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    ext = Path(file.filename or "icon.png").suffix.lower()
    if ext not in ALLOWED_IMG:
        raise HTTPException(400, f"Формат не поддерживается. Разрешены: {', '.join(ALLOWED_IMG)}")
    dest = DEVICE_ICONS_DIR / f"{device_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    icon_path = f"/static/icons/devices/{device_id}{ext}"
    await conn.execute("UPDATE devices SET icon_path=$1 WHERE id=$2", icon_path, device_id)
    return {"icon_path": icon_path}


# ── Categories ────────────────────────────────────────────────────────────────

@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreate,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    exists = await conn.fetchval("SELECT id FROM device_categories WHERE code=$1", body.code)
    if exists:
        raise HTTPException(400, "Категория с таким кодом уже существует")
    row = await conn.fetchrow(
        """INSERT INTO device_categories (code, name, icon, color, tab_id)
           VALUES ($1,$2,$3,$4,$5) RETURNING *""",
        body.code, body.name, body.icon, body.color, body.tab_id,
    )
    return dict(row)


@router.put("/categories/{cat_id}")
async def update_category(
    cat_id: int,
    body: CategoryUpdate,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    existing = await conn.fetchrow("SELECT id FROM device_categories WHERE id=$1", cat_id)
    if not existing:
        raise HTTPException(404, "Категория не найдена")

    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Нет данных для обновления")

    clauses, params = _build_update(updates)
    params.append(cat_id)

    row = await conn.fetchrow(
        f"UPDATE device_categories SET {', '.join(clauses)} WHERE id=${len(params)} RETURNING *",
        *params
    )
    return dict(row)


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category(
    cat_id: int,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    in_use = await conn.fetchval("SELECT COUNT(*) FROM devices WHERE category_id=$1", cat_id)
    if in_use and in_use > 0:
        raise HTTPException(400, f"Нельзя удалить: категория используется {in_use} устройствами")
    result = await conn.execute("DELETE FROM device_categories WHERE id=$1", cat_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Категория не найдена")


@router.post("/categories/{cat_id}/icon")
async def upload_cat_icon(
    cat_id: int,
    request: Request,
    file: UploadFile = File(...),
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    ext = Path(file.filename or "icon.png").suffix.lower()
    if ext not in ALLOWED_IMG:
        raise HTTPException(400, "Формат не поддерживается")
    dest = CAT_ICONS_DIR / f"{cat_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    icon_path = f"/static/icons/categories/{cat_id}{ext}"
    await conn.execute("UPDATE device_categories SET icon_path=$1 WHERE id=$2", icon_path, cat_id)
    return {"icon_path": icon_path}


# ── Zones ─────────────────────────────────────────────────────────────────────

@router.post("/zones", status_code=201)
async def create_zone(
    body: ZoneCreate,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    exists = await conn.fetchval("SELECT id FROM zones WHERE code=$1", body.code)
    if exists:
        raise HTTPException(400, "Зона с таким кодом уже существует")
    row = await conn.fetchrow(
        """INSERT INTO zones (name, code, color, description, lat_center, lon_center, radius_m)
           VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *""",
        body.name, body.code, body.color, body.description,
        body.lat_center, body.lon_center, body.radius_m,
    )
    return dict(row)


@router.put("/zones/{zone_id}")
async def update_zone(
    zone_id: int,
    body: ZoneUpdate,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    existing = await conn.fetchrow("SELECT id FROM zones WHERE id=$1", zone_id)
    if not existing:
        raise HTTPException(404, "Зона не найдена")

    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Нет данных для обновления")

    clauses, params = _build_update(updates)
    params.append(zone_id)

    row = await conn.fetchrow(
        f"UPDATE zones SET {', '.join(clauses)} WHERE id=${len(params)} RETURNING *",
        *params
    )
    return dict(row)


@router.delete("/zones/{zone_id}", status_code=204)
async def delete_zone(
    zone_id: int,
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    result = await conn.execute("DELETE FROM zones WHERE id=$1", zone_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Зона не найдена")
