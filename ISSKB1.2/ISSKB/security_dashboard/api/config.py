import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/config", tags=["config"])

LOGO_DIR = Path(__file__).parent.parent / "static" / "logo"
LOGO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
LOGO_PATH    = LOGO_DIR / "logo.png"  # canonical path (ext overwritten on upload)


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    ext = Path(file.filename or "logo.png").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Недопустимый формат. Разрешены: {', '.join(ALLOWED_EXTS)}")

    # Delete all existing logo files before saving new one
    for old in LOGO_DIR.glob("logo.*"):
        old.unlink(missing_ok=True)

    dest = LOGO_DIR / f"logo{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"logo_url": f"/static/logo/logo{ext}"}


@router.get("/logo")
async def get_logo():
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
        p = LOGO_DIR / f"logo{ext}"
        if p.exists():
            return {"logo_url": f"/static/logo/logo{ext}"}
    return {"logo_url": None}
