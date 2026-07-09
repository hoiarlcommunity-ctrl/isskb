"""
Сервис авторизации: хэширование паролей, JWT, refresh-токены.
"""
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt as _bcrypt
from jose import JWTError, jwt

from auth.config import (
    JWT_SECRET, JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_H, REFRESH_TOKEN_EXPIRE_D,
)


# ── Пароли (bcrypt напрямую, без passlib) ────────────────────────────────────

def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT access-токен ─────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str, role: str, office_id: str) -> str:
    now     = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_H)
    payload = {
        "sub":       str(user_id),
        "username":  username,
        "role":      role,
        "office_id": office_id,
        "exp":       expires,
        "iat":       now,
        "type":      "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


# ── Refresh-токен ─────────────────────────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    """Возвращает (raw_token, sha256_hash). В БД храним только hash."""
    raw    = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_D)
