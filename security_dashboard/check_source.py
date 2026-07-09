"""
Диагностика внешнего источника данных.
Запуск: python check_source.py [URL]

Пример: python check_source.py http://192.168.1.190/time.php?komandos=settings
"""
import sys
import asyncio
import json
import time

import httpx

sys.path.insert(0, ".")

DEFAULT_URL = "http://192.168.1.190/time.php?komandos=settings"


async def check(url: str):
    print(f"\n{'='*60}")
    print(f"  Диагностика источника данных")
    print(f"  URL: {url}")
    print(f"{'='*60}\n")

    print("[1] Подключение...")
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url)
        ms = round((time.monotonic() - t0) * 1000)
        print(f"    HTTP {r.status_code}  ({ms} мс)  Content-Type: {r.headers.get('content-type','?')}")
        print(f"    Размер ответа: {len(r.content)} байт")
    except httpx.ConnectError as e:
        print(f"    ОШИБКА: Нет соединения — {e}")
        return
    except httpx.TimeoutException:
        print("    ОШИБКА: Таймаут (10 сек)")
        return

    if r.status_code != 200:
        print(f"    ОШИБКА: Ожидался 200, получен {r.status_code}")
        return

    print("\n[2] Декодирование...")
    try:
        text = r.content.decode("utf-8")
        print("    Кодировка: UTF-8")
    except UnicodeDecodeError:
        text = r.content.decode("cp1251", errors="replace")
        print("    Кодировка: CP1251 (авто-фолбэк)")

    preview = text[:300].replace("\n", "\\n").replace("\r", "")
    print(f"    Первые 300 символов:\n    {preview}")

    print("\n[3] Определение формата...")
    records = []
    if text.lstrip().startswith("Array"):
        print("    Формат: PHP print_r()")
        from services.php_parser import parse_php_printout
        records = parse_php_printout(text)
    else:
        print("    Формат: JSON")
        try:
            data = json.loads(text)
            records = data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"    ОШИБКА JSON: {e}")
            print(f"\n    Сырой текст:\n{text[:800]}")
            return

    print(f"\n[4] Результат парсинга: {len(records)} устройств")
    for i, rec in enumerate(records[:5]):
        print(f"\n    Устройство #{i+1}:")
        for k, v in rec.items():
            vstr = str(v)[:80] + ("..." if len(str(v)) > 80 else "")
            print(f"      {k:20} = {vstr}")

    if len(records) > 5:
        print(f"\n    ... и ещё {len(records)-5} устройств")

    print(f"\n[5] Итог:")
    print(f"    ✓ Соединение: OK")
    print(f"    ✓ Ответ получен: {len(r.content)} байт")
    print(f"    ✓ Разобрано устройств: {len(records)}")
    if records:
        print(f"    ✓ Поля первого устройства: {list(records[0].keys())}")
    print()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    asyncio.run(check(url))
