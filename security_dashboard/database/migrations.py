import asyncpg
from .connection import DSN, _init_conn

SCHEMA_SQL = """
-- Device categories (иконку можно заменить своей через icon_path)
CREATE TABLE IF NOT EXISTS device_categories (
    id         SERIAL PRIMARY KEY,
    code       VARCHAR(50)  UNIQUE NOT NULL,
    name       VARCHAR(100) NOT NULL,
    icon       VARCHAR(10),
    icon_path  VARCHAR(500),
    color      VARCHAR(20)  DEFAULT '#3b82f6',
    tab_id     INTEGER      DEFAULT 5
);

-- Zones — географические зоны охраны объекта
-- Каждая зона — именованная область на карте (периметр, здание, двор и т.д.)
-- Устройства приписываются к зоне; инциденты связаны с зоной
CREATE TABLE IF NOT EXISTS zones (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    code        VARCHAR(50)  UNIQUE NOT NULL,
    color       VARCHAR(20)  DEFAULT '#3b82f6',
    description TEXT,
    lat_center  DECIMAL(10,7),
    lon_center  DECIMAL(10,7),
    radius_m    INTEGER DEFAULT 200
);

-- Devices
-- detection_ranges: JSON-массив зон охвата [{label, radius_m, color, opacity}]
-- icon_path: путь к загруженной иконке для этого конкретного устройства
-- Все поля метаданных (serial, ip, firmware и т.д.) — необязательные
CREATE TABLE IF NOT EXISTS devices (
    id                SERIAL PRIMARY KEY,
    category_id       INTEGER      NOT NULL REFERENCES device_categories(id),
    zone_id           INTEGER      REFERENCES zones(id),
    name              VARCHAR(200) NOT NULL,
    serial_number     VARCHAR(100),
    model             VARCHAR(100),
    manufacturer      VARCHAR(100),
    ip_address        VARCHAR(50),
    firmware_version  VARCHAR(50),
    installation_date DATE,
    is_mobile         BOOLEAN      DEFAULT FALSE,
    description       TEXT,
    responsible_person TEXT,
    icon_path         VARCHAR(500),
    detection_ranges  JSONB        DEFAULT '[]',
    created_at        TIMESTAMPTZ  DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  DEFAULT NOW()
);

-- Position history (только для мобильных устройств)
-- is_current=TRUE = актуальная позиция; остальное — история
-- Автоочистка: записи старше 24 ч удаляются при каждом обновлении позиции
CREATE TABLE IF NOT EXISTS device_positions (
    id          BIGSERIAL    PRIMARY KEY,
    device_id   INTEGER      NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    latitude    DECIMAL(10,7) NOT NULL,
    longitude   DECIMAL(10,7) NOT NULL,
    altitude    DECIMAL(8,2)  DEFAULT 0,
    heading     DECIMAL(5,2),
    speed       DECIMAL(6,2)  DEFAULT 0,
    is_current  BOOLEAN       DEFAULT FALSE,
    recorded_at TIMESTAMPTZ   DEFAULT NOW()
);

-- Device states — текущий снимок состояния каждого устройства
-- extra_state (JSONB) — гибкие метрики/статусы, специфичные для типа устройства
-- Примеры: {"fps":25,"pan_angle":120} для PTZ, {"smoke_density":0.02} для пожарного датчика
CREATE TABLE IF NOT EXISTS device_states (
    id               SERIAL       PRIMARY KEY,
    device_id        INTEGER      UNIQUE NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    online_status    BOOLEAN      DEFAULT FALSE,
    operational_mode VARCHAR(50)  DEFAULT 'idle',
    battery_level    SMALLINT,
    signal_strength  SMALLINT     DEFAULT 0,
    last_heartbeat   TIMESTAMPTZ,
    last_seen        TIMESTAMPTZ,
    error_code       VARCHAR(50),
    extra_state      JSONB        DEFAULT '{}',
    updated_at       TIMESTAMPTZ  DEFAULT NOW()
);

-- Device metrics — временной ряд телеметрии (история)
-- Отличие от device_states: здесь хранятся исторические измерения для графиков/трендов
-- payload (JSONB) — для составных метрик (например, координаты GPS, несколько значений за раз)
CREATE TABLE IF NOT EXISTS device_metrics (
    id           BIGSERIAL    PRIMARY KEY,
    device_id    INTEGER      NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    metric_key   VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4),
    unit         VARCHAR(20),
    payload      JSONB,
    recorded_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Operators
CREATE TABLE IF NOT EXISTS operators (
    id           SERIAL       PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    badge_number VARCHAR(50)  UNIQUE NOT NULL,
    role         VARCHAR(50)  DEFAULT 'operator',
    active       BOOLEAN      DEFAULT TRUE
);

-- Incidents
CREATE TABLE IF NOT EXISTS incidents (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id       INTEGER      REFERENCES devices(id) ON DELETE SET NULL,
    zone_id         INTEGER      REFERENCES zones(id) ON DELETE SET NULL,
    severity        VARCHAR(20)  NOT NULL,
    type            VARCHAR(50)  NOT NULL,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    status          VARCHAR(30)  DEFAULT 'open',
    operator_id     INTEGER      REFERENCES operators(id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- Incident comments — history of status changes and operator notes
CREATE TABLE IF NOT EXISTS incident_comments (
    id          SERIAL       PRIMARY KEY,
    incident_id UUID         NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    author      VARCHAR(200) DEFAULT 'Оператор',
    text        TEXT         NOT NULL,
    new_status  VARCHAR(30),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_inc_comments_incident ON incident_comments(incident_id, created_at DESC);

-- External devices — standalone staging table (no FK to main entities)
-- Populated by POST /api/external/devices; sync.py mirrors data into main DB
CREATE TABLE IF NOT EXISTS ext_devices (
    id          SERIAL       PRIMARY KEY,
    name        VARCHAR(200) NOT NULL UNIQUE,
    online      BOOLEAN      DEFAULT FALSE,
    status      VARCHAR(50)  DEFAULT 'unknown',
    latitude    DECIMAL(10,7),
    longitude   DECIMAL(10,7),
    received_at TIMESTAMPTZ  DEFAULT NOW(),
    synced_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_metrics_device_time   ON device_metrics(device_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_current     ON device_positions(device_id, is_current DESC);
CREATE INDEX IF NOT EXISTS idx_incidents_status_time ON incidents(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_states_device  ON device_states(device_id);
"""


async def run_migrations():
    conn = await asyncpg.connect(DSN)
    try:
        await _init_conn(conn)
        await conn.execute(SCHEMA_SQL)
        # Additive migrations for existing installations
        await conn.execute(
            "ALTER TABLE device_categories ADD COLUMN IF NOT EXISTS tab_id INTEGER DEFAULT 5"
        )
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS responsible_person TEXT"
        )
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS location VARCHAR(300)"
        )
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS notes TEXT"
        )
        await conn.execute(
            "ALTER TABLE ext_devices ADD COLUMN IF NOT EXISTS extra_data JSONB DEFAULT '{}'"
        )
        # New columns for external device integration
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS external_key VARCHAR(100)"
        )
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS port INTEGER"
        )
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS priority SMALLINT DEFAULT 0"
        )
        await conn.execute(
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS device_type VARCHAR(50)"
        )
        # Index for external_key lookups
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_devices_ext_key ON devices(external_key) WHERE external_key IS NOT NULL"
        )
        print("[DB] Schema applied (PostgreSQL)")
    finally:
        await conn.close()
