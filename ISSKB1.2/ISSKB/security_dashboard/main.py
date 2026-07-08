import asyncio
import sys
import json
import os
from pathlib import Path
from contextlib import asynccontextmanager

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware


class UTF8JSONResponse(Response):
    media_type = "application/json; charset=utf-8"

    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, default=str).encode("utf-8")


ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from database.connection import create_pool, close_pool
from database.migrations import run_migrations
from database.seed import run_seed
from api.devices import router as devices_router
from api.incidents import router as incidents_router
from api.zones import router as zones_router
from api.tiles import router as tiles_router
from api.categories import router as categories_router
from api.external import router as external_router
from api.config import router as config_router
from api.admin import router as admin_router
from api.admin_devices import router as admin_devices_router
from api.settings import router as settings_router
from websocket.manager import manager
from services.heartbeat import heartbeat_loop
from services.simulator import simulation_loop
from services.db_watcher import db_watcher_loop
from services.poller import poller_loop
from services.skyhunter_poller import skyhunter_loop
from services.imd_reader import imd_loop
import services.syslog as syslog
from auth.db import create_auth_pool, close_auth_pool
from auth.migrations import run_auth_migrations
from auth.router import router as auth_router
from auth.service import decode_access_token
from auth.config import COOKIE_NAME

# ── Пути, не требующие авторизации ───────────────────────────────────────────
_OPEN_PREFIXES = ("/auth/", "/static/", "/tiles/", "/login")
# Внешний приём данных должен проходить без браузерной cookie-сессии.
# Защита вынесена в api/external.py через X-API-Key/SENTINEL_EXTERNAL_TOKEN.
_OPEN_EXACT    = {"/ws", "/api/external/devices"}


_LOG_SKIP = {"/ws", "/auth/me", "/api/admin/logs", "/api/admin/metrics"}
_LOG_SKIP_PREFIXES = ("/static/", "/tiles/")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import time
        path = request.url.path
        t0 = time.monotonic()

        # Открытые маршруты
        if path in _OPEN_EXACT or any(path.startswith(p) for p in _OPEN_PREFIXES):
            return await call_next(request)

        token   = request.cookies.get(COOKIE_NAME)
        payload = decode_access_token(token) if token else None

        # Корень — перенаправляем на логин если нет сессии
        if path == "/":
            if not payload:
                return RedirectResponse("/login", status_code=302)
            return await call_next(request)

        # Панель администрирования — требует auth + роль admin
        if path == "/admin":
            if not payload:
                return RedirectResponse("/login", status_code=302)
            if payload.get("role") != "admin":
                return RedirectResponse("/", status_code=302)
            request.state.user = payload
            return await call_next(request)

        # API — 401 если нет сессии
        if path.startswith("/api/"):
            if not payload:
                return JSONResponse({"detail": "Необходима авторизация"}, status_code=401)
            request.state.user = payload
            return await call_next(request)

        response = await call_next(request)

        # Log API calls (skip noisy/internal paths)
        if (path.startswith("/api/") or path.startswith("/auth/")) \
                and path not in _LOG_SKIP \
                and not any(path.startswith(p) for p in _LOG_SKIP_PREFIXES):
            elapsed = round((time.monotonic() - t0) * 1000)
            method  = request.method
            status  = response.status_code
            user    = getattr(request.state, "user", {})
            who     = user.get("username", "аноним") if isinstance(user, dict) else "аноним"
            level   = "warn" if status >= 400 else "info"
            syslog.add(
                level, "api",
                f"{method} {path} → {status} ({elapsed}ms)",
                f"пользователь: {who} | IP: {request.client.host if request.client else '?'}",
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auth БД — первой, чтобы не блокировать запуск при ошибке основной БД
    await run_auth_migrations()
    app.state.auth_pool = await create_auth_pool()

    await run_migrations()
    app.state.db_pool = await create_pool()
    await run_seed()

    hb_task      = asyncio.create_task(heartbeat_loop())
    sim_task     = asyncio.create_task(simulation_loop())
    watcher_task = asyncio.create_task(db_watcher_loop())
    poll_task    = asyncio.create_task(poller_loop())
    sh_task      = asyncio.create_task(skyhunter_loop())
    imd_task     = asyncio.create_task(imd_loop())
    yield

    hb_task.cancel()
    sim_task.cancel()
    watcher_task.cancel()
    poll_task.cancel()
    sh_task.cancel()
    imd_task.cancel()
    await close_pool()
    await close_auth_pool()


app = FastAPI(
    title="Sentinel Command Center",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    default_response_class=UTF8JSONResponse,
)

app.add_middleware(AuthMiddleware)

app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(incidents_router)
app.include_router(zones_router)
app.include_router(tiles_router)
app.include_router(categories_router)
app.include_router(external_router)
app.include_router(config_router)
app.include_router(admin_router)
app.include_router(admin_devices_router)
app.include_router(settings_router)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(ws)


STATIC_DIR = ROOT / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))


@app.get("/admin", include_in_schema=False)
async def admin_panel():
    return FileResponse(str(STATIC_DIR / "admin.html"))


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading

    def _open_browser():
        import time
        time.sleep(1.8)
        webbrowser.open("http://127.0.0.1:8001")

    threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False, log_level="info")
