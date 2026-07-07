import os
import secrets

# В продакшене — обязательно установить через переменную окружения AUTH_JWT_SECRET
JWT_SECRET: str = os.getenv("AUTH_JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)
    print("[AUTH] WARNING: AUTH_JWT_SECRET не задан. Используется временный секрет — "
          "все сессии сбросятся при перезапуске. Задайте AUTH_JWT_SECRET в переменных среды.")

JWT_ALGORITHM          = "HS256"
ACCESS_TOKEN_EXPIRE_H  = 8       # время жизни access-токена (часы)
REFRESH_TOKEN_EXPIRE_D = 7       # время жизни refresh-токена (дни)
COOKIE_NAME            = "sentinel_auth"
COOKIE_REFRESH_NAME    = "sentinel_refresh"
MAX_FAILED_ATTEMPTS    = 5       # блокировка после N неудачных попыток
LOCKOUT_MINUTES        = 15      # длительность блокировки

AUTH_DSN = os.getenv(
    "AUTH_DSN",
    "postgresql://sentinel_user@127.0.0.1:5440/sentinel_auth"
)
