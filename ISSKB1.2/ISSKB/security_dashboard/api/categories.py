import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from database.connection import get_db_conn
import asyncpg

router = APIRouter(prefix="/api/categories", tags=["categories"])

ICONS_DIR = Path(__file__).parent.parent / "static" / "icons" / "categories"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


@router.get("")
async def list_categories(conn: asyncpg.Connection = Depends(get_db_conn)):
    rows = await conn.fetch("""
        SELECT dc.*, COUNT(d.id) AS device_count
        FROM device_categories dc
        LEFT JOIN devices d ON d.category_id = dc.id
        GROUP BY dc.id
        ORDER BY dc.name
    """)
    return [dict(r) for r in rows]


@router.post("/{category_id}/icon")
async def upload_category_icon(
    category_id: int,
    file: UploadFile = File(...),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    ext = Path(file.filename or "icon.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Недопустимый формат. Разрешены: {', '.join(ALLOWED_EXTS)}")

    dest = ICONS_DIR / f"{category_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    icon_path = f"/static/icons/categories/{category_id}{ext}"
    await conn.execute("UPDATE device_categories SET icon_path=$1 WHERE id=$2", icon_path, category_id)
    return {"icon_path": icon_path}
