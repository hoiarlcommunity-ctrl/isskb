"""
Схема БД sentinel_auth + создание учётной записи admin по умолчанию.
"""
import asyncpg
from auth.config import AUTH_DSN
from auth.service import hash_password


async def run_auth_migrations() -> None:
    conn = await asyncpg.connect(AUTH_DSN)
    try:
        await conn.execute("""
            -- Пользователи системы
            CREATE TABLE IF NOT EXISTS users (
                id               SERIAL PRIMARY KEY,
                username         VARCHAR(100) UNIQUE NOT NULL,
                password_hash    VARCHAR(255) NOT NULL,
                full_name        VARCHAR(200),
                role             VARCHAR(50)  NOT NULL DEFAULT 'operator',
                -- Роли: admin (главный офис, видит всё),
                --        operator (свой офис), viewer (только чтение)
                office_id        VARCHAR(50)  NOT NULL DEFAULT 'main',
                is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
                failed_attempts  INTEGER      NOT NULL DEFAULT 0,
                locked_until     TIMESTAMPTZ,
                last_login       TIMESTAMPTZ,
                created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
            );
            -- Расширенные поля для панели администрирования
            ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title   VARCHAR(200);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS phone       VARCHAR(50);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_work  VARCHAR(9);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS notes       TEXT;

            -- Refresh-токены (хранится только SHA-256 хэш, не raw)
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash  VARCHAR(64)  UNIQUE NOT NULL,
                expires_at  TIMESTAMPTZ  NOT NULL,
                revoked     BOOLEAN      NOT NULL DEFAULT FALSE,
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_rt_user_id ON refresh_tokens(user_id);
            CREATE INDEX IF NOT EXISTS idx_rt_hash    ON refresh_tokens(token_hash);

            -- Аудит-лог всех событий авторизации
            CREATE TABLE IF NOT EXISTS auth_audit (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                username    VARCHAR(100),
                action      VARCHAR(50)  NOT NULL,
                -- Действия: login_ok, login_fail, logout, token_refresh,
                --           account_locked, password_changed
                ip_address  VARCHAR(45),
                user_agent  TEXT,
                success     BOOLEAN      NOT NULL,
                detail      TEXT,
                created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_audit_user ON auth_audit(user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_ts   ON auth_audit(created_at DESC);
        """)

        # Создаём admin по умолчанию если таблица пуста
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count == 0:
            await conn.execute(
                """INSERT INTO users (username, password_hash, full_name, role, office_id)
                   VALUES ($1, $2, $3, 'admin', 'main')""",
                "admin",
                hash_password("Admin123!"),
                "Администратор",
            )
            print("[AUTH] ✓ Создан пользователь admin / Admin123!")
            print("[AUTH] ⚠  ОБЯЗАТЕЛЬНО смените пароль администратора при первом входе!")

    finally:
        await conn.close()
