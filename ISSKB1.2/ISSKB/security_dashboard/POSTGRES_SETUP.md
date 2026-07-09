# Портативный PostgreSQL (без Docker)

Начиная с этой версии сервер базы данных **поднимается вместе с приложением** —
Docker больше не нужен.

## Как это работает

- Бинарники PostgreSQL лежат в папке `pgsql/` (устанавливаются один раз).
- Данные кластера хранятся в `pgdata/` (создаётся автоматически при первом старте).
- Модуль [`database/embedded_pg.py`](database/embedded_pg.py) при запуске `main.py`:
  инициализирует кластер (только в первый раз), запускает сервер на порту **5440**,
  создаёт роль `sentinel_user` и базы `sentinel_isskb` / `sentinel_auth`.
  При остановке приложения сервер гасится.

## Первичная установка (один раз)

```powershell
powershell -ExecutionPolicy Bypass -File setup_postgres.ps1
```

Скрипт скачает официальные Windows-бинарники PostgreSQL и распакует их в `pgsql/`.
После этого просто запускайте `start.bat` — всё поднимется само.

## Доступ по сети (для других устройств)

Сервер слушает все интерфейсы (`listen_addresses = '*'`).
- **Локально** (само приложение, `127.0.0.1`) — вход без пароля (`trust`).
- **С других устройств в сети** — по паролю роли `sentinel_user`.
  Пароль по умолчанию — `sentinel123`, задаётся переменной окружения
  `SENTINEL_PG_PASSWORD`. Строка подключения с другого устройства:

  ```
  postgresql://sentinel_user:ПАРОЛЬ@IP_СЕРВЕРА:5440/sentinel_isskb
  ```

  Не забудьте открыть порт **5440** в брандмауэре Windows на сервере:
  ```powershell
  New-NetFirewallRule -DisplayName "Sentinel PostgreSQL" -Direction Inbound `
      -Protocol TCP -LocalPort 5440 -Action Allow
  ```

## Полезные переменные окружения

| Переменная               | По умолчанию | Назначение |
|--------------------------|--------------|------------|
| `SENTINEL_PG_PORT`       | `5440`       | Порт сервера |
| `SENTINEL_PG_PASSWORD`   | `sentinel123`| Пароль `sentinel_user` для сетевого доступа |
| `SENTINEL_PG_HOME`       | `./pgsql`    | Путь к бинарникам |
| `SENTINEL_PG_DATA`       | `./pgdata`   | Путь к данным кластера |
| `SENTINEL_PG_EMBEDDED`   | `1`          | `0` — не поднимать встроенный PG (использовать внешний) |

## Перенос данных из старого Docker-контейнера

Если в контейнере `sentinel-postgres` были важные данные, перенесите их так
(один раз, при работающем старом контейнере):

```powershell
# 1. Выгрузить обе базы из Docker
docker exec sentinel-postgres pg_dump -U sentinel_user sentinel_isskb > isskb.sql
docker exec sentinel-postgres pg_dump -U sentinel_user sentinel_auth  > auth.sql

# 2. Один раз запустить новое приложение (start.bat), чтобы создались базы,
#    затем загрузить дампы через встроенный psql:
pgsql\bin\psql -h 127.0.0.1 -p 5440 -U postgres -d sentinel_isskb -f isskb.sql
pgsql\bin\psql -h 127.0.0.1 -p 5440 -U postgres -d sentinel_auth  -f auth.sql
```

Если данные некритичны — этот шаг можно пропустить: схема и стартовые записи
создаются автоматически миграциями и сидом.
