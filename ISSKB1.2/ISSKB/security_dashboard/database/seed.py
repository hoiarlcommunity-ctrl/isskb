import asyncpg
import json
from datetime import datetime, timedelta
from .connection import DSN, _init_conn

# ── Категории — по подсистемам (tab_id) ──────────────────────────────────────
# (code, name, icon, color, tab_id)
CATEGORIES = [
    # Tab 1 — АИС "ПОЛЕ"
    ("cat_pole_cam",    "Камеры наблюдения",       "📷", "#3b82f6", 1),
    ("cat_pole_sensor", "Датчики периметра",       "🔊", "#60a5fa", 1),
    # Tab 2 — ВИП-117-М3
    ("cat_vip_kpp",     "КПП",                     "🔐", "#8b5cf6", 2),
    ("cat_vip_access",  "Системы доступа",         "🚪", "#a78bfa", 2),
    # Tab 3 — КАУС
    ("cat_kaus_server",  "Серверы управления",      "🖥", "#10b981", 3),
    ("cat_kaus_console", "Консоли оператора",       "🛡", "#34d399", 3),
    # Tab 4 — РАЗВЕДКА
    ("cat_razv_optic",  "Оптические посты",        "🔍", "#f59e0b", 4),
    ("cat_razv_radar",  "Радиолокаторы",           "📡", "#fbbf24", 4),
    # Tab 5 — РЭБ/РЭР
    ("cat_reb_jammer",  "Подавители",              "📡", "#ef4444", 5),
    ("cat_rer_sigint",  "Станции РЭР",             "🎧", "#f87171", 5),
    # Tab 6 — БпЛА
    ("cat_uav_copter",  "Мультироторные БпЛА",     "🚁", "#06b6d4", 6),
    ("cat_uav_wing",    "БпЛА самолётного типа",   "✈",  "#22d3ee", 6),
    ("cat_uav_station", "Станции управления БпЛА", "💻", "#67e8f9", 6),
    # Tab 7 — ОГНЕВЫЕ СРЕДСТВА ПОРАЖЕНИЯ
    ("cat_fire_turret", "Дистанционные модули",    "🔥", "#dc2626", 7),
    ("cat_fire_mortar", "Миномётные комплексы",    "💥", "#b91c1c", 7),
    # Tab 8 — НРКТ
    ("cat_nrkt_tracked", "Гусеничные платформы",   "🤖", "#7c3aed", 8),
    ("cat_nrkt_wheeled", "Колёсные платформы",     "🚗", "#a855f7", 8),
    # Tab 9 — ***
    ("cat_hq_comm",     "Связь и коммуникации",    "📞", "#0ea5e9", 9),
    ("cat_hq_power",    "Электропитание",          "⚡", "#38bdf8", 9),
]

# ── Устройства — район 56.011318, 37.847164 ──────────────────────────────────
# (name, serial, cat_code, lat, lon, is_mobile, mode, online, battery, description)
DEVICES = [
    # ─── Tab 1: АИС "ПОЛЕ" ───────────────────────────────────────────────────
    # Камеры наблюдения
    ("ВН-01 Периметр Север",   "POLE-001", "cat_pole_cam",    56.0320, 37.8480, False, "active",  True,  None, "PTZ-камера, сектор С"),
    ("ВН-02 Периметр Юг",      "POLE-002", "cat_pole_cam",    55.9905, 37.8460, False, "active",  True,  None, "PTZ-камера, сектор Ю"),
    ("ВН-03 КПП-1",            "POLE-003", "cat_pole_cam",    56.0145, 37.8340, False, "active",  True,  None, "Камера КПП-1"),
    ("ВН-04 Штаб",             "POLE-004", "cat_pole_cam",    56.0115, 37.8470, False, "active",  True,  None, "Камера штабного здания"),
    ("ВН-05 Плац",             "POLE-005", "cat_pole_cam",    56.0130, 37.8520, False, "idle",    False, None, "Камера плаца — не отвечает"),
    # Датчики периметра
    ("ДП-01 Сектор А",         "POLE-011", "cat_pole_sensor", 56.0340, 37.8350, False, "active",  True,  None, "Вибросейсмический"),
    ("ДП-02 Сектор Б",         "POLE-012", "cat_pole_sensor", 56.0340, 37.8600, False, "active",  True,  None, "ИК-барьер"),
    ("ДП-03 Сектор В",         "POLE-013", "cat_pole_sensor", 55.9890, 37.8350, False, "alarm",   True,  None, "Срабатывание — сектор В"),
    ("ДП-04 Сектор Г",         "POLE-014", "cat_pole_sensor", 55.9890, 37.8600, False, "active",  True,  None, "Радиолучевой"),

    # ─── Tab 2: ВИП-117-М3 ───────────────────────────────────────────────────
    # КПП
    ("КПП-1 Главный",          "VIP-001",  "cat_vip_kpp",     56.0145, 37.8335, False, "active",  True,  None, "Главный контрольно-пропускной пункт"),
    ("КПП-2 Технический",      "VIP-002",  "cat_vip_kpp",     56.0050, 37.8700, False, "active",  True,  None, "Технический въезд"),
    ("КПП-3 Запасной",         "VIP-003",  "cat_vip_kpp",     56.0280, 37.8280, False, "idle",    False, None, "Запасной — закрыт"),
    # Системы доступа
    ("Турникет Штаб",          "VIP-011",  "cat_vip_access",  56.0112, 37.8475, False, "active",  True,  None, "Биометрический контроль"),
    ("Замок Серверная",        "VIP-012",  "cat_vip_access",  56.0108, 37.8490, False, "active",  True,  None, "Электромагнитный замок"),
    ("Замок Арсенал",          "VIP-013",  "cat_vip_access",  56.0098, 37.8510, False, "active",  True,  None, "Электромеханический + PIN"),

    # ─── Tab 3: КАУС ─────────────────────────────────────────────────────────
    # Серверы управления
    ("Сервер ЦОД-1",           "KAUS-001", "cat_kaus_server",  56.0110, 37.8488, False, "active",  True,  None, "Основной сервер обработки"),
    ("Сервер ЦОД-2",           "KAUS-002", "cat_kaus_server",  56.0108, 37.8492, False, "active",  True,  None, "Резервный сервер"),
    ("Сервер БД",              "KAUS-003", "cat_kaus_server",  56.0106, 37.8496, False, "active",  True,  None, "Сервер базы данных"),
    # Консоли оператора
    ("АРМ Дежурного-1",        "KAUS-011", "cat_kaus_console", 56.0118, 37.8465, False, "active",  True,  None, "Автоматизированное рабочее место"),
    ("АРМ Дежурного-2",        "KAUS-012", "cat_kaus_console", 56.0120, 37.8462, False, "active",  True,  None, "АРМ сменного дежурного"),
    ("АРМ Командира",          "KAUS-013", "cat_kaus_console", 56.0125, 37.8458, False, "maintenance", True, None, "На обновлении ПО"),

    # ─── Tab 4: РАЗВЕДКА ─────────────────────────────────────────────────────
    # Оптические посты
    ("НП-1 Высота 215",        "RAZV-001", "cat_razv_optic",  56.0355, 37.8420, False, "active",  True,  None, "Наблюдательный пост, тепловизор"),
    ("НП-2 Роща",              "RAZV-002", "cat_razv_optic",  55.9880, 37.8520, False, "active",  True,  None, "Замаскированный НП"),
    ("НП-3 Восточный",         "RAZV-003", "cat_razv_optic",  56.0080, 37.8900, False, "idle",    False, None, "Оффлайн — замена питания"),
    # Радиолокаторы
    ("РЛС-1 Малой дальности",  "RAZV-011", "cat_razv_radar",  56.0290, 37.8550, False, "active",  True,  None, "Обзорная РЛС 10 км"),
    ("РЛС-2 Средней дальности","RAZV-012", "cat_razv_radar",  56.0200, 37.8300, False, "active",  True,  None, "РЛС обнаружения 30 км"),
    ("РЛС-3 Контрбатарейная",  "RAZV-013", "cat_razv_radar",  56.0150, 37.8650, False, "active",  True,  None, "Контрбатарейный радар"),
    ("Разведдозор-1",          "RAZV-021", "cat_razv_optic",  56.0180, 37.8400, True,  "patrol",  True,  78,   "Мобильный разведдозор СЗ"),

    # ─── Tab 5: РЭБ/РЭР ─────────────────────────────────────────────────────
    # Подавители
    ("Подавитель Р-330Ж",      "REB-001",  "cat_reb_jammer",  56.0260, 37.8500, False, "active",  True,  None, "Подавление каналов управления БпЛА"),
    ("Подавитель Р-934Б",      "REB-002",  "cat_reb_jammer",  56.0180, 37.8650, False, "active",  True,  None, "Широкополосное подавление"),
    ("Подавитель GPS/ГЛОНАСС", "REB-003",  "cat_reb_jammer",  56.0100, 37.8380, False, "active",  True,  None, "Подавление навигации"),
    ("Подавитель Р-330Ж-2",    "REB-004",  "cat_reb_jammer",  55.9950, 37.8550, False, "alarm",   True,  None, "Обнаружено излучение — работа"),
    # Станции РЭР
    ("Пост РЭР-1 Север",      "RER-001",  "cat_rer_sigint",  56.0330, 37.8450, False, "active",  True,  None, "Пеленгация + перехват"),
    ("Пост РЭР-2 Восток",     "RER-002",  "cat_rer_sigint",  56.0120, 37.8880, False, "active",  True,  None, "Пеленгация УКВ"),
    ("Пост РЭР-3 Юг",         "RER-003",  "cat_rer_sigint",  55.9910, 37.8420, False, "active",  True,  None, "Пеленгация СВЧ"),
    ("Мобильная станция РЭР",  "RER-004",  "cat_rer_sigint",  56.0200, 37.8550, True,  "patrol",  True,  62,   "Мобильный комплекс РЭР"),

    # ─── Tab 6: БпЛА ─────────────────────────────────────────────────────────
    # Мультироторные БпЛА
    ("Орлан-М1",               "UAV-001",  "cat_uav_copter",  56.0200, 37.8580, True,  "patrol",  True,  88,   "Квадрокоптер разведки"),
    ("Орлан-М2",               "UAV-002",  "cat_uav_copter",  56.0050, 37.8420, True,  "patrol",  True,  71,   "Квадрокоптер РЭБ"),
    ("Орлан-М3",               "UAV-003",  "cat_uav_copter",  56.0150, 37.8700, True,  "active",  True,  95,   "На базе — готов к вылету"),
    # БпЛА самолётного типа
    ("Орлан-10 №1",            "UAV-011",  "cat_uav_wing",    56.0300, 37.8600, True,  "patrol",  True,  54,   "Разведывательный БпЛА"),
    ("Орлан-10 №2",            "UAV-012",  "cat_uav_wing",    56.0100, 37.8350, False, "maintenance", True, None, "На ТО — замена двигателя"),
    # Станции управления
    ("НСУ-1 Центральная",      "UAV-021",  "cat_uav_station", 56.0115, 37.8500, False, "active",  True,  None, "Наземная станция управления"),
    ("НСУ-2 Полевая",          "UAV-022",  "cat_uav_station", 56.0220, 37.8420, False, "active",  True,  None, "Мобильная НСУ"),
    ("Ретранслятор БпЛА",      "UAV-023",  "cat_uav_station", 56.0340, 37.8500, False, "active",  True,  None, "Ретрансляция каналов управления"),

    # ─── Tab 7: ОГНЕВЫЕ СРЕДСТВА ПОРАЖЕНИЯ ───────────────────────────────────
    # Дистанционные модули
    ("ДУМ-1 Периметр С",       "FIRE-001", "cat_fire_turret", 56.0350, 37.8480, False, "active",  True,  None, "Дист. управляемый модуль — север"),
    ("ДУМ-2 Периметр В",       "FIRE-002", "cat_fire_turret", 56.0100, 37.8910, False, "active",  True,  None, "ДУМ — восток"),
    ("ДУМ-3 Периметр Ю",       "FIRE-003", "cat_fire_turret", 55.9880, 37.8480, False, "alarm",   True,  None, "ДУМ — юг, цель обнаружена"),
    # Миномётные комплексы
    ("Миномёт-1 Позиция А",    "FIRE-011", "cat_fire_mortar", 56.0250, 37.8300, False, "active",  True,  None, "82-мм автоматический"),
    ("Миномёт-2 Позиция Б",    "FIRE-012", "cat_fire_mortar", 55.9920, 37.8600, False, "active",  True,  None, "82-мм автоматический"),
    ("Миномёт-3 Позиция В",    "FIRE-013", "cat_fire_mortar", 56.0060, 37.8250, False, "idle",    False, None, "Не развёрнут"),

    # ─── Tab 8: НРКТ ─────────────────────────────────────────────────────────
    # Гусеничные платформы
    ("Маркер-М1",              "NRKT-001", "cat_nrkt_tracked", 56.0210, 37.8520, True,  "patrol",  True,  80,  "Гусеничный робот — патруль СВ"),
    ("Маркер-М2",              "NRKT-002", "cat_nrkt_tracked", 55.9960, 37.8380, True,  "patrol",  True,  65,  "Гусеничный робот — патруль Ю"),
    ("Маркер-М3",              "NRKT-003", "cat_nrkt_tracked", 56.0100, 37.8500, False, "maintenance", True, 100, "На зарядке"),
    # Колёсные платформы
    ("Нерехта-К1",             "NRKT-011", "cat_nrkt_wheeled", 56.0150, 37.8600, True,  "patrol",  True,  73,  "Колёсный робот — патруль В"),
    ("Нерехта-К2",             "NRKT-012", "cat_nrkt_wheeled", 56.0280, 37.8400, True,  "patrol",  True,  58,  "Колёсный робот — патруль СЗ"),
    ("Нерехта-К3",             "NRKT-013", "cat_nrkt_wheeled", 56.0050, 37.8480, False, "idle",    False, None, "Оффлайн — ремонт"),

    # ─── Tab 9: *** ──────────────────────────────────────────────────────────
    # Связь и коммуникации
    ("Р-168 Узел связи",       "HQ-001",  "cat_hq_comm",     56.0112, 37.8485, False, "active",  True,  None, "Цифровой узел связи"),
    ("Р-187 Ретранслятор",     "HQ-002",  "cat_hq_comm",     56.0350, 37.8500, False, "active",  True,  None, "Радиорелейная станция"),
    ("Р-166 Мобильная связь",  "HQ-003",  "cat_hq_comm",     56.0160, 37.8440, False, "active",  True,  None, "Мобильный комплекс связи"),
    # Электропитание
    ("ДГУ-1 Основная",         "HQ-011",  "cat_hq_power",    56.0105, 37.8500, False, "active",  True,  None, "Дизель-генератор 100 кВт"),
    ("ДГУ-2 Резервная",        "HQ-012",  "cat_hq_power",    56.0102, 37.8505, False, "idle",    True,  None, "Резервный генератор — ожидание"),
    ("ИБП Серверная",          "HQ-013",  "cat_hq_power",    56.0108, 37.8492, False, "active",  True,  None, "ИБП 30 кВА"),
]

# Зоны обнаружения
DETECTION_RANGES = {
    "RAZV-011": [
        {"label": "Зона обнаружения", "radius_m": 10000, "color": "#f59e0b", "opacity": 0.03},
        {"label": "Зона уверенного обнаружения", "radius_m": 5000, "color": "#f59e0b", "opacity": 0.06},
    ],
    "RAZV-012": [
        {"label": "Зона обнаружения", "radius_m": 30000, "color": "#fbbf24", "opacity": 0.02},
        {"label": "Зона сопровождения", "radius_m": 15000, "color": "#fbbf24", "opacity": 0.04},
    ],
    "RAZV-013": [
        {"label": "Зона обнаружения", "radius_m": 20000, "color": "#fbbf24", "opacity": 0.03},
    ],
    "REB-001": [
        {"label": "Зона подавления", "radius_m": 5000, "color": "#ef4444", "opacity": 0.04},
        {"label": "Зона воздействия", "radius_m": 2000, "color": "#ef4444", "opacity": 0.08},
    ],
    "REB-002": [
        {"label": "Зона подавления", "radius_m": 4000, "color": "#ef4444", "opacity": 0.04},
    ],
    "REB-003": [
        {"label": "Зона подавления GNSS", "radius_m": 3000, "color": "#ef4444", "opacity": 0.05},
    ],
    "FIRE-001": [
        {"label": "Зона поражения", "radius_m": 1500, "color": "#dc2626", "opacity": 0.06},
        {"label": "Зона обнаружения", "radius_m": 3000, "color": "#dc2626", "opacity": 0.03},
    ],
    "FIRE-002": [
        {"label": "Зона поражения", "radius_m": 1500, "color": "#dc2626", "opacity": 0.06},
        {"label": "Зона обнаружения", "radius_m": 3000, "color": "#dc2626", "opacity": 0.03},
    ],
    "FIRE-003": [
        {"label": "Зона поражения", "radius_m": 1500, "color": "#dc2626", "opacity": 0.06},
    ],
    "POLE-001": [
        {"label": "Зона обзора", "radius_m": 2000, "color": "#3b82f6", "opacity": 0.04},
    ],
    "POLE-002": [
        {"label": "Зона обзора", "radius_m": 2000, "color": "#3b82f6", "opacity": 0.04},
    ],
}

# Инциденты
INCIDENTS = [
    ("critical", "alarm",          "Тревога — Датчик периметра сектор В",
     "ДП-03 зафиксировал проникновение в секторе В. Требуется немедленная проверка.",
     "POLE-013"),
    ("high",     "alarm",          "РЭБ — обнаружено излучение",
     "Подавитель Р-330Ж-2 обнаружил управляющее излучение неизвестного БпЛА. Активировано подавление.",
     "REB-004"),
    ("high",     "alarm",          "ДУМ-3 — цель обнаружена",
     "Дистанционный модуль на южном периметре обнаружил движущуюся цель. Ожидание подтверждения.",
     "FIRE-003"),
    ("medium",   "device_offline", "ВН-05 Плац — потеря связи",
     "Камера плаца не отвечает более 15 минут. Возможно отключение питания.",
     "POLE-005"),
    ("medium",   "device_offline", "НП-3 Восточный — оффлайн",
     "Наблюдательный пост на восточном направлении не отвечает. Направлена группа замены питания.",
     "RAZV-003"),
    ("low",      "maintenance",    "АРМ Командира — обновление ПО",
     "Автоматизированное рабочее место командира переведено в режим обслуживания для установки обновлений.",
     "KAUS-013"),
    ("low",      "maintenance",    "Орлан-10 №2 — плановое ТО",
     "БпЛА самолётного типа на техническом обслуживании — замена двигателя.",
     "UAV-012"),
]


async def run_seed(force: bool = False):
    conn = await asyncpg.connect(DSN)
    try:
        await _init_conn(conn)

        count = await conn.fetchval("SELECT COUNT(*) FROM devices")
        if count and count > 0 and not force:
            print("[DB] Seed already applied — skipping")
            return

        if force or count == 0:
            await conn.execute("DELETE FROM incident_comments")
            await conn.execute("DELETE FROM incidents")
            await conn.execute("DELETE FROM device_metrics")
            await conn.execute("DELETE FROM device_states")
            await conn.execute("DELETE FROM device_positions")
            await conn.execute("DELETE FROM devices")
            await conn.execute("DELETE FROM zones")
            await conn.execute("DELETE FROM device_categories WHERE code LIKE 'cat_%' OR code = 'ext_device'")
            await conn.execute("DELETE FROM operators")

        # Категории
        cat_id_map: dict[str, int] = {}
        for code, name, icon, color, tab_id in CATEGORIES:
            row = await conn.fetchrow(
                """INSERT INTO device_categories (code, name, icon, color, tab_id)
                   VALUES ($1,$2,$3,$4,$5)
                   ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, tab_id=EXCLUDED.tab_id
                   RETURNING id""",
                code, name, icon, color, tab_id
            )
            cat_id_map[code] = row["id"]

        # Устройства
        now = datetime.utcnow()
        serial_to_id: dict[str, int] = {}

        for (name, serial, cat_code, lat, lon, is_mobile,
             mode, online, battery, desc) in DEVICES:

            cat_id = cat_id_map[cat_code]
            ranges = json.dumps(DETECTION_RANGES.get(serial, []))

            dev = await conn.fetchrow(
                """INSERT INTO devices
                       (category_id, name, serial_number, is_mobile, description,
                        detection_ranges, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$7) RETURNING id""",
                cat_id, name, serial, is_mobile, desc, ranges, now,
            )
            dev_id = dev["id"]
            serial_to_id[serial] = dev_id

            await conn.execute(
                """INSERT INTO device_positions
                       (device_id, latitude, longitude, is_current, recorded_at)
                   VALUES ($1,$2,$3,TRUE,$4)""",
                dev_id, lat, lon, now,
            )

            await conn.execute(
                """INSERT INTO device_states
                       (device_id, online_status, operational_mode, battery_level,
                        last_heartbeat, last_seen, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$5,$5)""",
                dev_id, online, mode, battery, now,
            )

        # Оператор
        op = await conn.fetchrow(
            """INSERT INTO operators (name, badge_number, role) VALUES ($1,$2,$3)
               ON CONFLICT (badge_number) DO UPDATE SET name=EXCLUDED.name RETURNING id""",
            "Дежурный оператор", "OP-001", "operator"
        )
        op_id = op["id"]

        # Инциденты
        for sev, typ, title, desc, serial in INCIDENTS:
            dev_id = serial_to_id.get(serial)
            ts = now - timedelta(minutes=30)
            status = "open"

            await conn.execute(
                """INSERT INTO incidents
                       (device_id, severity, type, title, description,
                        status, operator_id, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$8)""",
                dev_id, sev, typ, title, desc, status, op_id, ts,
            )

        print(f"[DB] Seed complete — {len(DEVICES)} devices, {len(INCIDENTS)} incidents")
    finally:
        await conn.close()
