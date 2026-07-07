# Схема базы данных — Sentinel Command Center

База данных: PostgreSQL (`sentinel`)  
Соединение: `postgresql://sentinel_user:sentinel123@localhost:5432/sentinel`

---

## Таблицы

### `device_categories` — Категории устройств

| Поле        | Тип           | Описание |
|-------------|---------------|----------|
| `id`        | SERIAL PK     | Уникальный идентификатор категории |
| `code`      | VARCHAR(50) UNIQUE | Машиночитаемый код (например, `cat_1`, `cat_2`) |
| `name`      | VARCHAR(100)  | Человекочитаемое название (например, «Категория 1») |
| `icon`      | VARCHAR(10)   | Emoji-иконка для отображения в интерфейсе |
| `icon_path` | VARCHAR(500)  | Путь к загруженному файлу иконки (PNG/SVG) — альтернатива emoji |
| `color`     | VARCHAR(20)   | HEX-цвет категории для маркеров и легенды (по умолчанию `#3b82f6`) |
| `tab_id`    | INTEGER       | ID вкладки подсистемы, к которой относится категория (по умолчанию 5) |

**Используется:** для группировки устройств по типу, фильтрации по слоям на карте, отображения в боковой панели.

---

### `zones` — Географические зоны

| Поле          | Тип             | Описание |
|---------------|-----------------|----------|
| `id`          | SERIAL PK       | Уникальный идентификатор зоны |
| `name`        | VARCHAR(100)    | Название зоны (например, «Периметр», «Здание А») |
| `code`        | VARCHAR(50) UNIQUE | Машиночитаемый код зоны |
| `color`       | VARCHAR(20)     | Цвет зоны на карте |
| `description` | TEXT            | Произвольное описание зоны |
| `lat_center`  | DECIMAL(10,7)   | Широта центра зоны |
| `lon_center`  | DECIMAL(10,7)   | Долгота центра зоны |
| `radius_m`    | INTEGER         | Радиус зоны в метрах (по умолчанию 200) |

**Используется:** для отображения именованных областей охраны на карте; устройства и инциденты могут быть привязаны к зоне.

---

### `devices` — Устройства

| Поле                 | Тип             | Описание |
|----------------------|-----------------|----------|
| `id`                 | SERIAL PK       | Уникальный идентификатор устройства |
| `category_id`        | INTEGER FK      | Ссылка на `device_categories.id` — категория устройства |
| `zone_id`            | INTEGER FK NULL | Ссылка на `zones.id` — зона размещения (необязательно) |
| `name`               | VARCHAR(200)    | Название устройства (например, «Устройство 1») |
| `serial_number`      | VARCHAR(100)    | Серийный номер (например, `SN-001`) |
| `model`              | VARCHAR(100)    | Модель устройства |
| `manufacturer`       | VARCHAR(100)    | Производитель |
| `ip_address`         | VARCHAR(50)     | IP-адрес (для сетевых устройств) |
| `firmware_version`   | VARCHAR(50)     | Версия прошивки |
| `installation_date`  | DATE            | Дата установки |
| `is_mobile`          | BOOLEAN         | `true` — подвижное устройство (участвует в симуляции патрулирования) |
| `description`        | TEXT            | Произвольное описание |
| `responsible_person` | TEXT            | ФИО ответственного за устройство (свободный текст) |
| `icon_path`          | VARCHAR(500)    | Путь к загруженной иконке конкретного устройства (PNG/SVG) |
| `detection_ranges`   | JSONB           | Массив зон охвата: `[{"label","radius_m","color","opacity"}]` |
| `created_at`         | TIMESTAMPTZ     | Дата создания записи |
| `updated_at`         | TIMESTAMPTZ     | Дата последнего обновления |

**Поле `detection_ranges`:** JSON-массив, описывающий зоны обнаружения/действия. Пример:
```json
[
  {"label": "Зона обнаружения", "radius_m": 3000, "color": "#3b82f6", "opacity": 0.05},
  {"label": "Зона действия",    "radius_m": 1000, "color": "#3b82f6", "opacity": 0.10}
]
```

**Загрузка иконки:** PUT/POST `/api/devices/{id}/icon` — файл сохраняется в `static/icons/devices/`, путь записывается в `icon_path`.

---

### `device_positions` — История позиций устройств

| Поле          | Тип              | Описание |
|---------------|------------------|----------|
| `id`          | BIGSERIAL PK     | Уникальный идентификатор записи позиции |
| `device_id`   | INTEGER FK       | Ссылка на `devices.id` |
| `latitude`    | DECIMAL(10,7)    | Широта |
| `longitude`   | DECIMAL(10,7)    | Долгота |
| `altitude`    | DECIMAL(8,2)     | Высота над уровнем моря (метры) |
| `heading`     | DECIMAL(5,2)     | Курс (градусы, 0–360) |
| `speed`       | DECIMAL(6,2)     | Скорость (м/с) |
| `is_current`  | BOOLEAN          | `true` — актуальная позиция; только одна запись на устройство |
| `recorded_at` | TIMESTAMPTZ      | Время записи координат |

**Индекс:** `idx_positions_current` по `(device_id, is_current DESC)`.  
**Ротация:** симулятор хранит не более 50 записей на устройство.

---

### `device_states` — Текущее состояние устройств

| Поле               | Тип           | Описание |
|--------------------|---------------|----------|
| `id`               | SERIAL PK     | Уникальный идентификатор записи состояния |
| `device_id`        | INTEGER UNIQUE FK | Ссылка на `devices.id` — одна строка на устройство |
| `online_status`    | BOOLEAN       | `true` — устройство онлайн |
| `operational_mode` | VARCHAR(50)   | Режим работы: `active`, `idle`, `alarm`, `warning`, `maintenance`, `patrol`, `offline` |
| `battery_level`    | SMALLINT      | Уровень заряда батареи (0–100, только для мобильных) |
| `signal_strength`  | SMALLINT      | Уровень сигнала (0–100, устарело — не используется в интерфейсе) |
| `last_heartbeat`   | TIMESTAMPTZ   | Время последнего успешного пинга |
| `last_seen`        | TIMESTAMPTZ   | Время последней активности |
| `error_code`       | VARCHAR(50)   | Код ошибки (если есть) |
| `extra_state`      | JSONB         | Дополнительные метрики, специфичные для типа устройства |
| `updated_at`       | TIMESTAMPTZ   | Время последнего обновления строки |

**Перевод в ТО:** PATCH `/api/devices/{id}` с `{"operational_mode":"maintenance"}` — автоматически создаёт инцидент типа `maintenance`.

---

### `device_metrics` — Телеметрия (временной ряд)

| Поле           | Тип             | Описание |
|----------------|-----------------|----------|
| `id`           | BIGSERIAL PK    | Уникальный идентификатор записи |
| `device_id`    | INTEGER FK      | Ссылка на `devices.id` |
| `metric_key`   | VARCHAR(100)    | Ключ метрики (например, `fps`, `temperature`, `speed`) |
| `metric_value` | DECIMAL(15,4)   | Числовое значение |
| `unit`         | VARCHAR(20)     | Единица измерения (например, `°C`, `м/с`) |
| `payload`      | JSONB           | Дополнительные данные (составные метрики) |
| `recorded_at`  | TIMESTAMPTZ     | Время измерения |

**Индекс:** `idx_metrics_device_time` по `(device_id, recorded_at DESC)`.

---

### `operators` — Операторы системы

| Поле           | Тип           | Описание |
|----------------|---------------|----------|
| `id`           | SERIAL PK     | Уникальный идентификатор оператора |
| `name`         | VARCHAR(200)  | ФИО оператора |
| `badge_number` | VARCHAR(50) UNIQUE | Табельный номер (например, `OP-001`) |
| `role`         | VARCHAR(50)   | Роль: `operator`, `supervisor`, `admin` |
| `active`       | BOOLEAN       | Активен ли аккаунт |

---

### `incidents` — Инциденты

| Поле              | Тип           | Описание |
|-------------------|---------------|----------|
| `id`              | UUID PK       | Уникальный идентификатор инцидента (генерируется автоматически) |
| `device_id`       | INTEGER FK NULL | Ссылка на `devices.id` — устройство, связанное с инцидентом |
| `zone_id`         | INTEGER FK NULL | Ссылка на `zones.id` — зона инцидента |
| `severity`        | VARCHAR(20)   | Критичность: `critical`, `high`, `medium`, `low`, `info` |
| `type`            | VARCHAR(50)   | Тип: `alarm`, `device_offline`, `maintenance`, `warning`, etc. |
| `title`           | VARCHAR(200)  | Краткое заглавие инцидента |
| `description`     | TEXT          | Подробное описание |
| `status`          | VARCHAR(30)   | Статус: `open` (открыт), `in_progress` (в работе), `closed` (закрыт) |
| `operator_id`     | INTEGER FK NULL | Ссылка на `operators.id` — назначенный оператор |
| `acknowledged_at` | TIMESTAMPTZ   | Время подтверждения инцидента |
| `resolved_at`     | TIMESTAMPTZ   | Время закрытия инцидента |
| `created_at`      | TIMESTAMPTZ   | Время создания |
| `updated_at`      | TIMESTAMPTZ   | Время последнего обновления |

**Автосоздание:** при переводе устройства в режим ТО автоматически создаётся инцидент со статусом `in_progress` и типом `maintenance`.  
**Индекс:** `idx_incidents_status_time` по `(status, created_at DESC)`.

---

### `incident_comments` — Комментарии к инцидентам

| Поле           | Тип           | Описание |
|----------------|---------------|----------|
| `id`           | SERIAL PK     | Уникальный идентификатор комментария |
| `incident_id`  | UUID FK       | Ссылка на `incidents.id` (CASCADE DELETE) |
| `author`       | VARCHAR(200)  | Имя автора (по умолчанию «Оператор») |
| `text`         | TEXT          | Текст комментария |
| `new_status`   | VARCHAR(30)   | Новый статус инцидента (если комментарий создан при смене статуса) |
| `created_at`   | TIMESTAMPTZ   | Время создания комментария |

**Автосоздание:** при каждой смене статуса через PATCH `/api/incidents/{id}/status` автоматически добавляется комментарий с текстом «Статус изменён на …» и необязательным комментарием оператора.  
**Индекс:** `idx_inc_comments_incident` по `(incident_id, created_at DESC)`.

---

### `ext_devices` — Внешние устройства (буфер)

| Поле           | Тип             | Описание |
|----------------|-----------------|----------|
| `id`           | SERIAL PK       | Уникальный идентификатор |
| `name`         | VARCHAR(200) UNIQUE | Название устройства из внешней системы |
| `online`       | BOOLEAN         | Статус онлайн (из внешнего источника) |
| `status`       | VARCHAR(50)     | Статус устройства в строковом виде |
| `latitude`     | DECIMAL(10,7)   | Широта (из внешнего источника) |
| `longitude`    | DECIMAL(10,7)   | Долгота (из внешнего источника) |
| `received_at`  | TIMESTAMPTZ     | Время получения данных от внешней системы |
| `synced_at`    | TIMESTAMPTZ     | Время синхронизации в основную таблицу `devices` |

**Используется:** данные от внешней системы поступают через POST `/api/external/devices`. Если устройство с таким именем уже есть в `devices` — обновляется его статус. Если нет — создаётся новое.

---

## API-эндпоинты (сводка)

| Метод   | Путь                                  | Описание |
|---------|---------------------------------------|----------|
| GET     | `/api/devices`                        | Список всех устройств с состоянием и позицией |
| GET     | `/api/devices/{id}`                   | Детальная информация + метрики устройства |
| PATCH   | `/api/devices/{id}`                   | Обновление `operational_mode` и/или `responsible_person` |
| POST    | `/api/devices/{id}/icon`              | Загрузка иконки устройства (PNG/SVG) |
| GET     | `/api/incidents`                      | Список инцидентов (фильтр по `status`, `severity`) |
| PATCH   | `/api/incidents/{id}/status`          | Смена статуса инцидента с автокомментарием |
| GET     | `/api/incidents/{id}/comments`        | Список комментариев к инциденту |
| POST    | `/api/incidents/{id}/comments`        | Добавление комментария к инциденту |
| POST    | `/api/external/devices`               | Приём данных от внешней системы |
| GET     | `/api/config/logo`                    | Текущий URL логотипа |
| POST    | `/api/config/logo`                    | Загрузка нового логотипа (PNG/SVG) |
| GET     | `/api/categories`                     | Список категорий устройств |
| GET     | `/api/zones`                          | Список зон |
| WS      | `/ws`                                 | WebSocket для real-time обновлений |

---

## WebSocket-события

| Тип события       | Описание |
|-------------------|----------|
| `state_update`    | Обновление состояния устройств (online_status, operational_mode) |
| `position_update` | Обновление координат мобильных устройств (каждые 3 сек.) |
| `device_updated`  | Полное обновление устройства (после PATCH) |
| `incident_updated`| Обновление статуса инцидента |
| `incident_new`    | Новый инцидент |
| `metrics_update`  | Телеметрия устройств |
| `ext_heartbeat`   | Результат проверки внешнего сервера (ok/error) |
