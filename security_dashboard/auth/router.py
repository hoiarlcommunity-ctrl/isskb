"""
Эндпоинты авторизации: /auth/login, /auth/logout, /auth/refresh, /auth/me
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, Field

from auth.config import (
    COOKIE_NAME, COOKIE_REFRESH_NAME,
    ACCESS_TOKEN_EXPIRE_H, MAX_FAILED_ATTEMPTS, LOCKOUT_MINUTES,
)
from auth.db import get_auth_pool
from auth.service import (
    verify_password, create_access_token, decode_access_token,
    generate_refresh_token, hash_refresh_token, refresh_token_expiry,
)

router = APIRouter(prefix="/auth", tags=["auth"])


from typing import Optional

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class ProfileUpdate(BaseModel):
    full_name:  Optional[str] = Field(None, max_length=200)
    job_title:  Optional[str] = Field(None, max_length=200)
    phone:      Optional[str] = Field(None, max_length=50)
    phone_work: Optional[str] = Field(None, max_length=9)
    notes:      Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password:     str = Field(..., min_length=6, max_length=200)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME, value=token,
        httponly=True, samesite="lax", secure=False,
        max_age=ACCESS_TOKEN_EXPIRE_H * 3600,
        path="/",
    )


def _set_refresh_cookie(response: Response, raw: str, expires_at: datetime) -> None:
    ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    response.set_cookie(
        key=COOKIE_REFRESH_NAME, value=raw,
        httponly=True, samesite="lax", secure=False,
        max_age=ttl, path="/auth/refresh",
    )


async def _audit(pool, user_id, username, action, request: Request, success: bool, detail: str = ""):
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")[:300]
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO auth_audit (user_id, username, action, ip_address, user_agent, success, detail)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                user_id, username, action, ip, ua, success, detail,
            )
    except Exception:
        pass  # Аудит не должен прерывать основной поток


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    pool = get_auth_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE username=$1", body.username
        )

    # Пользователь не найден — даём тот же ответ что и при неверном пароле
    if not user:
        await _audit(pool, None, body.username, "login_fail", request, False, "user not found")
        raise HTTPException(401, "Неверное имя пользователя или пароль")

    # Проверка активности
    if not user["is_active"]:
        await _audit(pool, user["id"], user["username"], "login_fail", request, False, "account inactive")
        raise HTTPException(403, "Учётная запись отключена")

    # Проверка блокировки
    if user["locked_until"] and user["locked_until"] > datetime.now(timezone.utc):
        remaining = int((user["locked_until"] - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        await _audit(pool, user["id"], user["username"], "login_fail", request, False, "account locked")
        raise HTTPException(429, f"Учётная запись временно заблокирована. Осталось: {remaining} мин.")

    # Проверка пароля
    if not verify_password(body.password, user["password_hash"]):
        new_attempts = user["failed_attempts"] + 1
        async with pool.acquire() as conn:
            if new_attempts >= MAX_FAILED_ATTEMPTS:
                from datetime import timedelta
                locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
                await conn.execute(
                    "UPDATE users SET failed_attempts=$1, locked_until=$2 WHERE id=$3",
                    new_attempts, locked_until, user["id"]
                )
                await _audit(pool, user["id"], user["username"], "account_locked", request, False,
                             f"locked for {LOCKOUT_MINUTES} min after {new_attempts} attempts")
                raise HTTPException(429, f"Превышено число попыток. Блокировка на {LOCKOUT_MINUTES} мин.")
            else:
                await conn.execute(
                    "UPDATE users SET failed_attempts=$1 WHERE id=$2",
                    new_attempts, user["id"]
                )
        await _audit(pool, user["id"], user["username"], "login_fail", request, False,
                     f"wrong password, attempt {new_attempts}")
        raise HTTPException(401, "Неверное имя пользователя или пароль")

    # Успешный вход — сбрасываем счётчик, обновляем last_login
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET failed_attempts=0, locked_until=NULL, last_login=NOW() WHERE id=$1",
            user["id"]
        )

    # Создаём токены
    access_token = create_access_token(
        user_id=user["id"], username=user["username"],
        role=user["role"], office_id=user["office_id"],
    )
    raw_refresh, hash_refresh = generate_refresh_token()
    exp = refresh_token_expiry()

    async with pool.acquire() as conn:
        # Инвалидируем старые refresh-токены пользователя (одна активная сессия)
        await conn.execute(
            "UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=$1 AND revoked=FALSE",
            user["id"]
        )
        await conn.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1,$2,$3)",
            user["id"], hash_refresh, exp,
        )

    _set_auth_cookie(response, access_token)
    _set_refresh_cookie(response, raw_refresh, exp)

    await _audit(pool, user["id"], user["username"], "login_ok", request, True)

    return {
        "ok": True,
        "user": {
            "id":        user["id"],
            "username":  user["username"],
            "full_name": user["full_name"],
            "role":      user["role"],
            "office_id": user["office_id"],
        }
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = decode_access_token(token)
        if payload:
            pool = get_auth_pool()
            await _audit(pool, int(payload["sub"]), payload["username"], "logout", request, True)
            # Отзываем все refresh-токены
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=$1",
                    int(payload["sub"])
                )

    response.delete_cookie(COOKIE_NAME, path="/")
    response.delete_cookie(COOKIE_REFRESH_NAME, path="/auth/refresh")
    return {"ok": True}


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    raw = request.cookies.get(COOKIE_REFRESH_NAME)
    if not raw:
        raise HTTPException(401, "Refresh-токен отсутствует")

    hashed = hash_refresh_token(raw)
    pool   = get_auth_pool()

    async with pool.acquire() as conn:
        rt = await conn.fetchrow(
            """SELECT rt.*, u.username, u.role, u.office_id, u.is_active
               FROM refresh_tokens rt JOIN users u ON u.id = rt.user_id
               WHERE rt.token_hash=$1""",
            hashed
        )

    if not rt or rt["revoked"] or rt["expires_at"] < datetime.now(timezone.utc):
        response.delete_cookie(COOKIE_NAME, path="/")
        response.delete_cookie(COOKIE_REFRESH_NAME, path="/auth/refresh")
        raise HTTPException(401, "Refresh-токен недействителен или истёк")

    if not rt["is_active"]:
        raise HTTPException(403, "Учётная запись отключена")

    # Ротация refresh-токена
    new_raw, new_hash = generate_refresh_token()
    new_exp = refresh_token_expiry()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE refresh_tokens SET revoked=TRUE WHERE token_hash=$1", hashed)
        await conn.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1,$2,$3)",
            rt["user_id"], new_hash, new_exp,
        )

    access_token = create_access_token(
        user_id=rt["user_id"], username=rt["username"],
        role=rt["role"], office_id=rt["office_id"],
    )
    _set_auth_cookie(response, access_token)
    _set_refresh_cookie(response, new_raw, new_exp)

    await _audit(pool, rt["user_id"], rt["username"], "token_refresh", request, True)
    return {"ok": True}


@router.get("/me")
async def get_me(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Токен недействителен или истёк")
    user_id = int(payload["sub"])
    pool = get_auth_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT full_name, job_title, phone, phone_work, notes FROM users WHERE id=$1", user_id
        )
    return {
        "id":         user_id,
        "username":   payload["username"],
        "role":       payload["role"],
        "office_id":  payload["office_id"],
        "full_name":  row["full_name"]  if row else None,
        "job_title":  row["job_title"]  if row else None,
        "phone":      row["phone"]      if row else None,
        "phone_work": row["phone_work"] if row else None,
        "notes":      row["notes"]      if row else None,
    }


@router.put("/profile")
async def update_profile(body: ProfileUpdate, request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Токен недействителен или истёк")
    user_id = int(payload["sub"])

    updates = body.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "Нет данных для обновления")

    set_parts = []
    params = []
    for i, (k, v) in enumerate(updates.items(), start=1):
        set_parts.append(f"{k}=${i}")
        params.append(v)
    set_parts.append("updated_at=NOW()")
    params.append(user_id)

    pool = get_auth_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE users SET {', '.join(set_parts)} WHERE id=${len(params)}"
            " RETURNING full_name, job_title, phone, phone_work, notes",
            *params,
        )
    return dict(row) if row else {}


@router.put("/profile/password")
async def change_password(body: PasswordChange, request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Не авторизован")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Токен недействителен или истёк")
    user_id = int(payload["sub"])

    pool = get_auth_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT password_hash FROM users WHERE id=$1", user_id)
        if not row:
            raise HTTPException(404, "Пользователь не найден")
        if not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(400, "Текущий пароль неверен")
        from auth.service import hash_password
        await conn.execute(
            "UPDATE users SET password_hash=$1, updated_at=NOW() WHERE id=$2",
            hash_password(body.new_password), user_id,
        )
        await conn.execute(
            "UPDATE refresh_tokens SET revoked=TRUE WHERE user_id=$1", user_id
        )
    return {"ok": True}
