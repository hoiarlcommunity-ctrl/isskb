"""Административный API — пользователи, аудит, сессии, состояние системы. Только роль admin."""
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field

from auth.db import get_auth_pool
from auth.service import hash_password
from database.connection import get_db_conn
import asyncpg

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(request: Request) -> dict:
    user = getattr(request.state, 'user', None)
    if not user or user.get('role') != 'admin':
        raise HTTPException(403, "Недостаточно прав доступа")
    return user


def _gen_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%"),
    ]
    pwd += [secrets.choice(chars) for _ in range(length - 4)]
    rng = secrets.SystemRandom()
    rng.shuffle(pwd)
    return ''.join(pwd)


# ── Pydantic models ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=6, max_length=200)
    full_name: Optional[str] = Field(None, max_length=200)
    role: str = Field("operator")
    office_id: str = Field("main", max_length=50)
    job_title: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    phone_work: Optional[str] = Field(None, max_length=9)
    notes: Optional[str] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=200)
    role: Optional[str] = None
    office_id: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=50)
    phone_work: Optional[str] = Field(None, max_length=9)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: Optional[str] = Field(None, min_length=6, max_length=200)
    generate: bool = False


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(request: Request, _: dict = Depends(require_admin)):
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, username, full_name, role, office_id, job_title, phone, phone_work, notes,
                      is_active, failed_attempts, locked_until, last_login, created_at, updated_at
               FROM users ORDER BY id"""
        )
    return [dict(r) for r in rows]


@router.post("/users", status_code=201)
async def create_user(body: UserCreate, request: Request, _: dict = Depends(require_admin)):
    if body.role not in ('admin', 'operator', 'viewer'):
        raise HTTPException(400, "Роль должна быть: admin, operator или viewer")
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT id FROM users WHERE username=$1", body.username)
        if exists:
            raise HTTPException(400, "Пользователь с таким именем уже существует")
        row = await conn.fetchrow(
            """INSERT INTO users (username, password_hash, full_name, role, office_id,
                                  job_title, phone, phone_work, notes, is_active)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
               RETURNING id, username, full_name, role, office_id, job_title,
                         phone, phone_work, notes, is_active, created_at""",
            body.username, hash_password(body.password), body.full_name,
            body.role, body.office_id, body.job_title, body.phone,
            body.phone_work, body.notes, body.is_active,
        )
    return dict(row)


@router.get("/users/{user_id}")
async def get_user(user_id: int, request: Request, _: dict = Depends(require_admin)):
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, username, full_name, role, office_id, job_title, phone, phone_work, notes,
                      is_active, failed_attempts, locked_until, last_login, created_at, updated_at
               FROM users WHERE id=$1""",
            user_id
        )
    if not row:
        raise HTTPException(404, "Пользователь не найден")
    return dict(row)


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, request: Request, _: dict = Depends(require_admin)):
    if body.role and body.role not in ('admin', 'operator', 'viewer'):
        raise HTTPException(400, "Недопустимая роль")
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE id=$1", user_id)
        if not existing:
            raise HTTPException(404, "Пользователь не найден")

        updates = body.dict(exclude_unset=True)
        if not updates:
            raise HTTPException(400, "Нет данных для обновления")

        set_clauses = []
        params = []
        i = 1
        for k, v in updates.items():
            set_clauses.append(f"{k}=${i}")
            params.append(v)
            i += 1
        set_clauses.append("updated_at=NOW()")
        params.append(user_id)

        row = await conn.fetchrow(
            f"""UPDATE users SET {', '.join(set_clauses)} WHERE id=${i}
                RETURNING id, username, full_name, role, office_id, job_title,
                          phone, phone_work, notes, is_active, updated_at""",
            *params
        )
    return dict(row)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, request: Request, _: dict = Depends(require_admin)):
    current = getattr(request.state, 'user', {})
    if str(user_id) == str(current.get('sub', '')):
        raise HTTPException(400, "Нельзя удалить собственную учётную запись")
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM users WHERE id=$1", user_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Пользователь не найден")


@router.post("/users/{user_id}/reset-password")
async def reset_password(user_id: int, body: PasswordReset, request: Request, _: dict = Depends(require_admin)):
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, username FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(404, "Пользователь не найден")

        if body.generate:
            new_pwd = _gen_password()
        elif body.new_password:
            new_pwd = body.new_password
        else:
            raise HTTPException(400, "Укажите new_password или generate=true")

        await conn.execute(
            "UPDATE users SET password_hash=$1, failed_attempts=0, locked_until=NULL, updated_at=NOW() WHERE id=$2",
            hash_password(new_pwd), user_id
        )
        await conn.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=$1", user_id)
        await conn.execute(
            """INSERT INTO auth_audit (user_id, username, action, ip_address, success, detail)
               VALUES ($1,$2,'password_changed',$3,TRUE,'Сброс пароля администратором')""",
            user_id, row['username'],
            request.client.host if request.client else 'unknown'
        )

    result_data: dict = {"ok": True, "username": row['username']}
    if body.generate:
        result_data["generated_password"] = new_pwd
    return result_data


@router.post("/users/{user_id}/unlock")
async def unlock_user(user_id: int, request: Request, _: dict = Depends(require_admin)):
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET failed_attempts=0, locked_until=NULL, updated_at=NOW() WHERE id=$1",
            user_id
        )
        if result == "UPDATE 0":
            raise HTTPException(404, "Пользователь не найден")
    return {"ok": True}


# ── Audit ─────────────────────────────────────────────────────────────────────

@router.get("/audit")
async def get_audit(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    username: Optional[str] = None,
    action: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    conditions = ["1=1"]
    filter_params: list = []
    i = 1
    if username:
        conditions.append(f"username ILIKE ${i}")
        filter_params.append(f"%{username}%")
        i += 1
    if action:
        conditions.append(f"action=${i}")
        filter_params.append(action)
        i += 1

    where = ' AND '.join(conditions)
    page_params = list(filter_params) + [min(limit, 500), max(offset, 0)]

    pool = get_auth_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""SELECT id, user_id, username, action, ip_address, success, detail, created_at
                FROM auth_audit WHERE {where}
                ORDER BY created_at DESC LIMIT ${i} OFFSET ${i+1}""",
            *page_params
        )
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM auth_audit WHERE {where}", *filter_params
        )
    return {"total": total, "items": [dict(r) for r in rows]}


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def get_sessions(request: Request, _: dict = Depends(require_admin)):
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT rt.user_id, u.username, u.full_name, u.role, u.office_id,
                      rt.created_at, rt.expires_at
               FROM refresh_tokens rt
               JOIN users u ON u.id = rt.user_id
               WHERE rt.revoked=FALSE AND rt.expires_at > NOW()
               ORDER BY rt.created_at DESC"""
        )
    return [dict(r) for r in rows]


@router.delete("/sessions/{user_id}", status_code=204)
async def revoke_user_sessions(user_id: int, request: Request, _: dict = Depends(require_admin)):
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=$1", user_id)


# ── DB Status ─────────────────────────────────────────────────────────────────

@router.get("/db-status")
async def get_db_status(
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    results = {}

    auth_pool = get_auth_pool()
    try:
        async with auth_pool.acquire() as ac:
            user_count = await ac.fetchval("SELECT COUNT(*) FROM users")
        results["auth_db"] = {"status": "ok", "database": "sentinel_auth", "users": int(user_count)}
    except Exception as e:
        results["auth_db"] = {"status": "error", "error": str(e)}

    try:
        device_count = await conn.fetchval("SELECT COUNT(*) FROM devices")
        incident_count = await conn.fetchval("SELECT COUNT(*) FROM incidents WHERE status != 'closed'")
        results["main_db"] = {
            "status": "ok",
            "database": "sentinel_isskb",
            "devices": int(device_count),
            "open_incidents": int(incident_count),
        }
    except Exception as e:
        results["main_db"] = {"status": "error", "error": str(e)}

    return results


# ── System metrics ────────────────────────────────────────────────────────────

@router.get("/metrics")
async def get_metrics(
    request: Request,
    _: dict = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
):
    import time
    import psutil
    import os

    result: dict = {}

    # ── Process & OS metrics ──────────────────────────────────────────────────
    try:
        proc = psutil.Process(os.getpid())
        cpu_pct  = psutil.cpu_percent(interval=0.1)
        mem      = psutil.virtual_memory()
        proc_mem = proc.memory_info()
        boot_ts  = psutil.boot_time()
        uptime_s = int(time.time() - boot_ts)

        result["system"] = {
            "cpu_percent":      round(cpu_pct, 1),
            "cpu_count":        psutil.cpu_count(logical=True),
            "ram_total_mb":     round(mem.total / 1024 / 1024),
            "ram_used_mb":      round(mem.used  / 1024 / 1024),
            "ram_percent":      round(mem.percent, 1),
            "process_rss_mb":   round(proc_mem.rss / 1024 / 1024, 1),
            "os_uptime_s":      uptime_s,
        }
    except Exception as e:
        result["system"] = {"error": str(e)}

    # ── Main DB (sentinel_isskb) ───────────────────────────────────────────────
    try:
        t0 = time.monotonic()
        db_name = await conn.fetchval("SELECT current_database()")
        db_size_bytes = await conn.fetchval(f"SELECT pg_database_size($1)", db_name)
        active_conns  = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_stat_activity WHERE state='active' AND datname=$1", db_name
        )
        idle_conns    = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_stat_activity WHERE state='idle' AND datname=$1", db_name
        )
        total_conns   = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_stat_activity WHERE datname=$1", db_name
        )
        device_count  = await conn.fetchval("SELECT COUNT(*) FROM devices")
        incident_count= await conn.fetchval("SELECT COUNT(*) FROM incidents WHERE status != 'closed'")
        db_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        result["main_db"] = {
            "status":          "ok",
            "database":        db_name,
            "size_mb":         round(db_size_bytes / 1024 / 1024, 2) if db_size_bytes else 0,
            "active_conns":    int(active_conns  or 0),
            "idle_conns":      int(idle_conns    or 0),
            "total_conns":     int(total_conns   or 0),
            "devices":         int(device_count  or 0),
            "open_incidents":  int(incident_count or 0),
            "latency_ms":      db_latency_ms,
        }
    except Exception as e:
        result["main_db"] = {"status": "error", "error": str(e)}

    # ── Auth DB (sentinel_auth) ────────────────────────────────────────────────
    auth_pool = get_auth_pool()
    try:
        t0 = time.monotonic()
        async with auth_pool.acquire() as ac:
            auth_db_name  = await ac.fetchval("SELECT current_database()")
            auth_db_size  = await ac.fetchval(f"SELECT pg_database_size($1)", auth_db_name)
            user_count    = await ac.fetchval("SELECT COUNT(*) FROM users WHERE is_active=TRUE")
            session_count = await ac.fetchval(
                "SELECT COUNT(*) FROM refresh_tokens WHERE revoked=FALSE AND expires_at > NOW()"
            )
            auth_conns    = await ac.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname=$1", auth_db_name
            )
            auth_latency  = round((time.monotonic() - t0) * 1000, 1)

        result["auth_db"] = {
            "status":        "ok",
            "database":      auth_db_name,
            "size_mb":       round(auth_db_size / 1024 / 1024, 2) if auth_db_size else 0,
            "total_conns":   int(auth_conns  or 0),
            "active_users":  int(user_count  or 0),
            "active_sessions": int(session_count or 0),
            "latency_ms":    auth_latency,
        }
    except Exception as e:
        result["auth_db"] = {"status": "error", "error": str(e)}

    return result


# ── Server restart ────────────────────────────────────────────────────────────

@router.get("/logs")
async def get_logs(
    limit:    int = 200,
    category: str | None = None,
    level:    str | None = None,
    _: dict = Depends(require_admin),
):
    import services.syslog as syslog
    return syslog.get(limit=limit, category=category or None, level=level or None)


@router.post("/server/restart")
async def restart_server(request: Request, _: dict = Depends(require_admin)):
    import asyncio
    import os
    import sys

    async def _do_restart():
        await asyncio.sleep(1.5)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.create_task(_do_restart())
    return {"ok": True, "message": "Перезапуск через 1.5 секунды"}
