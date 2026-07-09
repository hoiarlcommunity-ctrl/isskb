"""
Встроенный (портативный) PostgreSQL — поднимается вместе с приложением, без Docker.

Идея: бинарники PostgreSQL лежат рядом с программой в папке ``pgsql/`` (их один
раз кладёт ``setup_postgres.ps1``). Кластер данных живёт в ``pgdata/``. При первом
запуске кластер инициализируется, настраивается сеть и создаются роль
``sentinel_user`` + базы ``sentinel_isskb`` / ``sentinel_auth``. При каждом старте
приложения сервер поднимается через ``pg_ctl``, при остановке — гасится.

Локальные подключения (127.0.0.1) идут по ``trust`` — поэтому DSN приложения
(``sentinel_user@127.0.0.1:5440`` без пароля) работает как раньше, код запросов
менять не нужно. Для устройств в локальной сети открыт доступ по паролю
(scram-sha-256), сервер слушает все интерфейсы.

Переменные окружения (необязательные):
  SENTINEL_PG_PORT      — порт (по умолчанию 5440)
  SENTINEL_PG_PASSWORD  — пароль роли sentinel_user для сетевого доступа
  SENTINEL_PG_HOME      — путь к бинарникам PostgreSQL (по умолчанию ./pgsql)
  SENTINEL_PG_DATA      — путь к кластеру данных (по умолчанию ./pgdata)
  SENTINEL_PG_EMBEDDED  — "0" полностью отключает встроенный запуск
                          (используется внешний/ручной PostgreSQL)
"""
from __future__ import annotations

import os
import sys
import time
import shutil
import socket
import subprocess
from pathlib import Path

# Корень проекта — папка security_dashboard (родитель этого модуля/пакета database)
ROOT = Path(__file__).resolve().parent.parent

PG_HOME = Path(os.getenv("SENTINEL_PG_HOME", str(ROOT / "pgsql")))
PG_DATA = Path(os.getenv("SENTINEL_PG_DATA", str(ROOT / "pgdata")))
PG_PORT = int(os.getenv("SENTINEL_PG_PORT", "5440"))
PG_PASSWORD = os.getenv("SENTINEL_PG_PASSWORD", "sentinel123")

# Суперпользователь кластера (только для служебных операций bootstrap)
SUPERUSER = "postgres"
# Прикладная роль, под которой работает приложение
APP_ROLE = "sentinel_user"
APP_DBS = ("sentinel_isskb", "sentinel_auth")

LOG_FILE = PG_DATA / "pg.log"


def _bin(name: str) -> Path:
    """Путь к утилите PostgreSQL внутри pgsql/bin (с .exe на Windows)."""
    exe = name + (".exe" if os.name == "nt" else "")
    return PG_HOME / "bin" / exe


def _env() -> dict:
    """Окружение для дочерних процессов: bin в PATH (чтобы находились DLL)."""
    env = os.environ.copy()
    env["PATH"] = str(PG_HOME / "bin") + os.pathsep + env.get("PATH", "")
    # initdb/psql могут ругаться на не-ASCII локаль/кодировку — фиксируем UTF-8
    env["PGCLIENTENCODING"] = "UTF8"
    return env


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    """Запустить утилиту PostgreSQL и вернуть результат (без исключения)."""
    return subprocess.run(
        args, env=_env(), capture_output=True, text=True, encoding="utf-8",
        errors="replace", **kw,
    )


def is_enabled() -> bool:
    return os.getenv("SENTINEL_PG_EMBEDDED", "1") != "0"


def binaries_present() -> bool:
    return _bin("pg_ctl").exists() and _bin("initdb").exists()


def _cluster_initialized() -> bool:
    return (PG_DATA / "PG_VERSION").exists()


def _port_open(host: str = "127.0.0.1", port: int | None = None) -> bool:
    """Проверить, слушает ли кто-то порт (сервер уже запущен)."""
    port = port or PG_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


# ── Инициализация кластера ────────────────────────────────────────────────────

def _init_cluster() -> None:
    print(f"[PG] Первый запуск — инициализация кластера в {PG_DATA} …")
    PG_DATA.parent.mkdir(parents=True, exist_ok=True)

    # Пароль суперпользователя передаём через файл (безопаснее, чем в argv)
    pwfile = PG_DATA.parent / ".pg_superpw.tmp"
    pwfile.write_text(PG_PASSWORD, encoding="utf-8")
    try:
        res = _run([
            str(_bin("initdb")),
            "-D", str(PG_DATA),
            "-U", SUPERUSER,
            "--auth-local=trust",
            "--auth-host=trust",           # временно; ужесточим в pg_hba ниже
            "--pwfile", str(pwfile),
            "--encoding=UTF8",
            "--locale=C",
            "-E", "UTF8",
        ])
    finally:
        try:
            pwfile.unlink()
        except OSError:
            pass

    if res.returncode != 0:
        raise RuntimeError(f"initdb завершился с ошибкой:\n{res.stdout}\n{res.stderr}")

    _write_conf()
    _write_hba()
    print("[PG] Кластер инициализирован.")


def _write_conf() -> None:
    """Донастройка postgresql.conf: порт и прослушивание всех интерфейсов."""
    conf = PG_DATA / "postgresql.conf"
    extra = (
        "\n# ── Sentinel: настройки встроенного PostgreSQL ──\n"
        f"port = {PG_PORT}\n"
        "listen_addresses = '*'\n"
        "password_encryption = scram-sha-256\n"
        "max_connections = 100\n"
    )
    with conf.open("a", encoding="utf-8") as f:
        f.write(extra)


def _write_hba() -> None:
    """pg_hba.conf: локально — trust (для приложения), в сети — по паролю."""
    hba = PG_DATA / "pg_hba.conf"
    rules = (
        "# ── Sentinel: правила доступа ──\n"
        "# Локальные подключения приложения — без пароля (trust)\n"
        "local   all   all                         trust\n"
        "host    all   all   127.0.0.1/32          trust\n"
        "host    all   all   ::1/128               trust\n"
        "# Устройства в локальной сети — по паролю\n"
        "host    all   all   0.0.0.0/0             scram-sha-256\n"
        "host    all   all   ::/0                  scram-sha-256\n"
    )
    hba.write_text(rules, encoding="utf-8")


# ── Управление процессом сервера ──────────────────────────────────────────────

def _pg_ctl(action: str, *extra: str) -> tuple[int, str]:
    """Запустить pg_ctl. Возвращает (код возврата, текст вывода).

    ВАЖНО: здесь НЕЛЬЗЯ использовать PIPE (capture_output). При действии
    ``start`` pg_ctl порождает долгоживущий процесс postmaster, который на
    Windows наследует хэндлы наших пайпов и держит их открытыми. subprocess.run
    тогда бесконечно ждёт EOF на пайпе — и весь запуск приложения зависает.
    Поэтому пишем вывод во временный файл: файловый хэндл наследуется без
    блокировки, и subprocess.run корректно возвращается, как только pg_ctl
    завершился.
    """
    outfile = PG_DATA.parent / ".pgctl.log"
    with open(outfile, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(
            [str(_bin("pg_ctl")), "-D", str(PG_DATA), "-l", str(LOG_FILE),
             *extra, action],
            env=_env(), stdout=fh, stderr=subprocess.STDOUT,
        )
    try:
        text = outfile.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    return proc.returncode, text


def _wait_ready(timeout: float = 30.0) -> None:
    """Дождаться, пока сервер начнёт принимать подключения."""
    deadline = time.time() + timeout
    isready = _bin("pg_isready")
    while time.time() < deadline:
        if isready.exists():
            r = _run([str(isready), "-h", "127.0.0.1", "-p", str(PG_PORT)])
            if r.returncode == 0:
                return
        elif _port_open():
            return
        time.sleep(0.4)
    raise RuntimeError(f"PostgreSQL не поднялся за {timeout} c. См. {LOG_FILE}")


def _psql(dbname: str, sql: str) -> subprocess.CompletedProcess:
    return _run([
        str(_bin("psql")),
        "-h", "127.0.0.1", "-p", str(PG_PORT),
        "-U", SUPERUSER, "-d", dbname,
        "-v", "ON_ERROR_STOP=1",
        "-tAc", sql,
    ])


def _ensure_role_and_dbs() -> None:
    """Создать роль sentinel_user и базы, если их ещё нет."""
    # Роль
    exists = _psql("postgres", f"SELECT 1 FROM pg_roles WHERE rolname='{APP_ROLE}'")
    if exists.stdout.strip() != "1":
        print(f"[PG] Создаю роль {APP_ROLE} …")
        _psql(
            "postgres",
            f"CREATE ROLE {APP_ROLE} LOGIN SUPERUSER "
            f"PASSWORD '{PG_PASSWORD}'",
        )
    else:
        # Обновляем пароль на актуальный (на случай смены SENTINEL_PG_PASSWORD)
        _psql("postgres", f"ALTER ROLE {APP_ROLE} PASSWORD '{PG_PASSWORD}'")

    # Базы
    for db in APP_DBS:
        exists = _psql("postgres", f"SELECT 1 FROM pg_database WHERE datname='{db}'")
        if exists.stdout.strip() != "1":
            print(f"[PG] Создаю базу {db} …")
            r = _psql("postgres", f'CREATE DATABASE "{db}" OWNER {APP_ROLE}')
            if r.returncode != 0:
                raise RuntimeError(f"Не удалось создать базу {db}:\n{r.stderr}")


# ── Публичный API ─────────────────────────────────────────────────────────────

def start() -> None:
    """Поднять встроенный PostgreSQL. Идемпотентно."""
    if not is_enabled():
        print("[PG] Встроенный PostgreSQL отключён (SENTINEL_PG_EMBEDDED=0). "
              "Ожидается внешний сервер.")
        return

    if not binaries_present():
        raise RuntimeError(
            "Бинарники PostgreSQL не найдены в "
            f"{PG_HOME}. Запустите один раз setup_postgres.ps1, "
            "чтобы скачать портативный PostgreSQL."
        )

    if _port_open():
        print(f"[PG] Порт {PG_PORT} уже занят — считаю, что сервер уже запущен.")
        _ensure_role_and_dbs()
        return

    if not _cluster_initialized():
        _init_cluster()

    print(f"[PG] Запуск PostgreSQL (порт {PG_PORT}) …")
    rc, out = _pg_ctl("start", "-w", "-o", f"-p {PG_PORT}")
    if rc != 0:
        raise RuntimeError(f"pg_ctl start не удался:\n{out}")

    _wait_ready()
    _ensure_role_and_dbs()
    print("[PG] PostgreSQL готов.")


def stop() -> None:
    """Остановить встроенный PostgreSQL (если мы его запускали)."""
    if not is_enabled() or not binaries_present() or not _cluster_initialized():
        return
    print("[PG] Остановка PostgreSQL …")
    _pg_ctl("stop", "-m", "fast", "-w")
