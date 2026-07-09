"""
Built-in IMD-07 reader for ISSKB, no GUI, no pyserial.

This version intentionally mirrors New_program_IMD-7/main.py:
- COM settings: 9600 8N2, DTR=false, RTS=true by default
- packet framing and CRC are copied from the working GUI parser
- payload is sent directly to services.sync.sync_to_main(), then WebSocket update

Enable in config/imd.json:
{
  "enabled": true,
  "port": "COM6",
  "debug_raw": false
}
"""
from __future__ import annotations

import asyncio
import ctypes
import json
import re
import struct
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

from database.connection import get_pool
from services.sync import sync_to_main
from websocket.manager import manager

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config" / "imd.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "port": "COM6",
    "baudrate": 9600,
    "stopbits": 2,
    "timeout": 0.5,
    "dtr": False,
    "rts": True,
    "reconnect_interval": 5,
    "send_interval": 5,
    "no_signal_timeout": 8,
    "device_name": "ИМД-07",
    "lat": 55.7558,
    "lon": 37.6173,
    "debug_raw": False,
    "debug_crc": False,
    "thresholds": {
        "pult_dr": 0.500,
        "pult_ed": 5.0,
        "vbd_dr": 0.500,
        "vbd_beta": 0.5,
        "vbd_alpha": 0.03,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print("[IMD] config/imd.json должен быть JSON-объектом; сервис отключён")
            return dict(DEFAULT_CONFIG)
        return _deep_merge(DEFAULT_CONFIG, data)
    except Exception as exc:
        print(f"[IMD] Не удалось прочитать config/imd.json: {exc}; сервис отключён")
        return dict(DEFAULT_CONFIG)


async def imd_loop() -> None:
    cfg = _load_config()
    if not cfg.get("enabled"):
        print("[IMD] Built-in IMD reader disabled (config/imd.json: enabled=false)")
        return

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    stop_event = threading.Event()

    worker = threading.Thread(
        target=_reader_worker,
        args=(cfg, loop, queue, stop_event),
        daemon=True,
        name="imd07-reader",
    )
    worker.start()
    print(f"[IMD] Built-in IMD reader started: port={cfg.get('port')}")

    try:
        while True:
            payload = await queue.get()
            await _publish_payload(payload)
    except asyncio.CancelledError:
        stop_event.set()
        await asyncio.to_thread(worker.join, 2.0)
        print("[IMD] Built-in IMD reader stopped")
        raise


async def _publish_payload(payload: dict[str, Any]) -> None:
    pool = get_pool()
    if pool is None:
        print("[IMD] DB pool is not ready; packet skipped")
        return

    # Важно: запись time-series метрик не должна ломать live-обновление
    # карточки.  Раньше один длинный raw-пакет попадал в unit VARCHAR(20),
    # _store_imd_metrics падал, и WebSocket event не отправлялся.  Поэтому
    # сначала синхронизируем устройство и готовим live device_updated, а
    # метрики пишем отдельным best-effort шагом.
    try:
        device = None
        metrics_event = None
        result = None
        async with pool.acquire() as conn:
            result = await sync_to_main(conn, [payload], field_map=None)
            dev_id = await conn.fetchval("SELECT id FROM devices WHERE LOWER(name)=LOWER($1)", str(payload.get("name") or ""))
            device = await _fetch_device_for_broadcast(conn, str(payload.get("name") or ""), payload)

            if dev_id:
                try:
                    metrics_event = await _store_imd_metrics(conn, int(dev_id), payload)
                except Exception as metric_exc:
                    print(f"[IMD] metrics store warning: {metric_exc}")

        # Точечный WebSocket update. Нельзя слать devices_updated для ИМД:
        # браузер будет каждые несколько секунд перезагружать /api/devices,
        # из-за чего все маркеры и списки визуально исчезают/появляются.
        if device:
            await manager.broadcast("device_updated", device)
        else:
            await manager.broadcast("devices_updated", result or {})
        if metrics_event:
            await manager.broadcast("metrics_update", [metrics_event])

        print(
            f"[IMD] synced: {payload.get('name')} | "
            f"status={payload.get('status')} | dose={payload.get('dose_rate', '—')} | {result}"
        )
    except Exception as exc:
        print(f"[IMD] DB sync error: {exc}")


async def _fetch_device_for_broadcast(conn, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return device shape for the UI and always attach current IMD extra_state.

    Some /api/devices serializers in this project do not include device_states.extra_state
    in the list/detail response.  If we broadcast only the serialized DB row, the
    right panel receives just numeric metrics and loses IMD-specific values
    (режим, питание, время, raw packet, status bytes, thresholds, ВБД fields).
    Therefore the live WebSocket event carries the freshly decoded payload as
    extra_state as well.
    """
    if not name.strip():
        return None
    try:
        from api.devices import _DEVICE_SELECT, _serialize

        row = await conn.fetchrow(_DEVICE_SELECT + " WHERE LOWER(d.name) = LOWER($1)", name)
        if not row:
            return None
        device = _serialize(row)

        # Merge DB extra_state and the current decoded packet.  The payload is
        # authoritative for the current tick and guarantees that the UI can show
        # all fields immediately, without waiting for /api/devices/{id}.
        merged_extra: dict[str, Any] = {}
        try:
            dev_id = int(device.get("id") or row.get("id"))
            db_extra = await conn.fetchval("SELECT extra_state FROM device_states WHERE device_id=$1", dev_id)
            if isinstance(db_extra, str):
                db_extra = json.loads(db_extra)
            if isinstance(db_extra, dict):
                merged_extra.update(db_extra)
        except Exception:
            pass

        if payload:
            merged_extra.update(_payload_extra_fields(payload))

        if merged_extra:
            device["extra_state"] = merged_extra
        return device
    except Exception as exc:
        print(f"[IMD] device broadcast fetch error: {exc}")
        return None


def _payload_extra_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Fields that should be visible in the ПОКАЗАТЕЛИ panel."""
    hidden = {"name", "online", "status", "device_type", "battery_level", "lat", "lon", "latitude", "longitude"}
    return {
        k: v for k, v in payload.items()
        if k not in hidden and v is not None and str(v) != ""
    }


_NUM_RE = re.compile(r"[-+−±\s]*([0-9]+(?:[.,][0-9]+)?)\s*(.*)")


def _split_num_unit(value: Any) -> tuple[float | None, str | None, str]:
    raw = "" if value is None else str(value).strip()
    if not raw or raw == "—":
        return None, None, raw
    m = _NUM_RE.match(raw.replace("−", "-"))
    if not m:
        return None, None, raw
    try:
        num = float(m.group(1).replace(",", "."))
    except Exception:
        return None, None, raw
    unit = (m.group(2) or "").strip() or None
    return num, unit, raw


# Эти значения внешне могут начинаться с цифры/hex, но это НЕ числовые
# метрики с unit.  Например raw-пакет начинается с "01 0c ..."; старый
# парсер воспринимал "01" как число, а весь остаток как unit и PostgreSQL
# падал на VARCHAR(20).
_STRING_ONLY_METRIC_KEYS = {
    "vbd_data",
    "imd_mode",
    "imd_time",
    "imd_power",
    "imd_ext_type",
    "imd_alarm_pult_dr",
    "imd_alarm_pult_ed",
    "imd_alarm_vbd",
    "imd_last_error",
    "imd_packet_type",
    "imd_crc",
    "imd_status_byte",
    "imd_error_byte",
    "imd_low_battery",
    "imd_external_power",
    "imd_raw_packet",
}


def _metric_db_value(key: str, raw: str) -> tuple[float, str | None, bool]:
    """Return (numeric_value, unit, string_metric).

    device_metrics is a numeric time-series table with short VARCHAR units.
    IMD also has display-only fields (hex bytes, packet type, raw packet).
    Store display-only values in payload.raw and use numeric 0 for DB value.
    The UI receives raw text through metrics_update and extra_state.
    """
    if key in _STRING_ONLY_METRIC_KEYS:
        return 0.0, None, True

    num, unit, _ = _split_num_unit(raw)
    if num is None:
        return 0.0, None, True

    # Safety: device_metrics.unit in the project schema is short.  If a value
    # was misdetected and produced a long unit, treat it as display-only text
    # instead of breaking the whole IMD update cycle.
    if unit is not None and len(str(unit)) > 20:
        return 0.0, None, True

    return num, unit, False


async def _store_imd_metrics(conn, device_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Store current IMD fields in device_metrics without blocking UI updates.

    Every field is still sent to the browser as raw display text.  DB insert is
    best-effort per metric: one bad/long field must not stop the next live
    packet from appearing in the ИМД card.
    """
    event_metrics = []

    for key, raw_value in _payload_extra_fields(payload).items():
        raw = str(raw_value)
        if not raw or raw in ("None",):
            continue

        # metric_key may also be VARCHAR(20) in older schemas.  Do not lose UI
        # update if somebody adds a longer IMD key later: broadcast it, but skip
        # time-series insert.
        if len(str(key)) > 20:
            event_metrics.append({"key": key, "value": 0.0, "unit": None, "raw": raw})
            continue

        metric_value, metric_unit, string_metric = _metric_db_value(key, raw)
        payload_json = json.dumps(
            {"raw": raw, "display": raw, "string_metric": string_metric},
            ensure_ascii=False,
        )

        try:
            await conn.execute(
                """INSERT INTO device_metrics (device_id, metric_key, metric_value, unit, payload, recorded_at)
                   VALUES ($1::integer, $2::text, $3::numeric, $4::text, $5::jsonb, NOW())""",
                device_id,
                key,
                metric_value,
                metric_unit,
                payload_json,
            )
        except Exception as exc:
            # Do not abort the whole packet.  The value is still sent to UI via
            # metrics_update and stored in device_states.extra_state by sync_to_main().
            print(f"[IMD] metric skipped: {key} ({exc})")

        event_metrics.append({"key": key, "value": metric_value, "unit": metric_unit, "raw": raw})

    return {"device_id": device_id, "metrics": event_metrics} if event_metrics else None

def _emit(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue, payload: dict[str, Any]) -> None:
    def _put() -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass

    loop.call_soon_threadsafe(_put)


class SerialException(OSError):
    pass


class _WinSerial:
    """Small pyserial-like Windows COM reader used by ISSKB only."""

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        stopbits: float = 2,
        timeout: float = 0.5,
        dtr: bool = False,
        rts: bool = True,
    ) -> None:
        self.port = port
        self.baudrate = int(baudrate)
        self.stopbits = float(stopbits)
        self.timeout = float(timeout)
        self._dtr = bool(dtr)
        self._rts = bool(rts)
        self._handle: wintypes.HANDLE | None = None

    @property
    def dtr(self) -> bool:
        return self._dtr

    @property
    def rts(self) -> bool:
        return self._rts

    @property
    def is_open(self) -> bool:
        return self._handle is not None and int(self._handle.value or 0) not in (-1, 0)

    def _kernel32(self):
        if not hasattr(ctypes, "WinDLL"):
            raise SerialException("Встроенный COM-reader поддерживает только Windows")
        return ctypes.WinDLL("kernel32", use_last_error=True)

    def open(self) -> None:
        if self.is_open:
            return
        if not self.port:
            raise SerialException("COM-порт не задан")

        kernel32 = self._kernel32()
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

        name = str(self.port)
        if not name.startswith("\\\\.\\"):
            name = "\\\\.\\" + name

        handle = kernel32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None)
        handle_value = int(handle or 0)
        if handle_value in (0, INVALID_HANDLE_VALUE):
            err = ctypes.get_last_error()
            raise SerialException(err, f"Не удалось открыть {self.port}")

        self._handle = wintypes.HANDLE(handle_value)
        try:
            self._setup_comm()
        except Exception:
            self.close()
            raise

    def _setup_comm(self) -> None:
        kernel32 = self._kernel32()

        class DCB(ctypes.Structure):
            _fields_ = [
                ("DCBlength", wintypes.DWORD),
                ("BaudRate", wintypes.DWORD),
                ("Flags", wintypes.DWORD),
                ("wReserved", wintypes.WORD),
                ("XonLim", wintypes.WORD),
                ("XoffLim", wintypes.WORD),
                ("ByteSize", ctypes.c_ubyte),
                ("Parity", ctypes.c_ubyte),
                ("StopBits", ctypes.c_ubyte),
                ("XonChar", ctypes.c_char),
                ("XoffChar", ctypes.c_char),
                ("ErrorChar", ctypes.c_char),
                ("EofChar", ctypes.c_char),
                ("EvtChar", ctypes.c_char),
                ("wReserved1", wintypes.WORD),
            ]

        class COMMTIMEOUTS(ctypes.Structure):
            _fields_ = [
                ("ReadIntervalTimeout", wintypes.DWORD),
                ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
                ("ReadTotalTimeoutConstant", wintypes.DWORD),
                ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
                ("WriteTotalTimeoutConstant", wintypes.DWORD),
            ]

        if not kernel32.SetupComm(self._handle, 4096, 4096):
            raise SerialException(ctypes.get_last_error(), "SetupComm failed")

        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        if not kernel32.GetCommState(self._handle, ctypes.byref(dcb)):
            raise SerialException(ctypes.get_last_error(), "GetCommState failed")

        # Same effective configuration as New_program_IMD-7/main.py with pyserial:
        # 9600, 8 data bits, no parity, 2 stop bits, DTR=false, RTS=true.
        DTR_CONTROL_DISABLE = 0
        DTR_CONTROL_ENABLE = 1
        RTS_CONTROL_DISABLE = 0
        RTS_CONTROL_ENABLE = 1

        dcb.BaudRate = int(self.baudrate)
        dcb.ByteSize = 8
        dcb.Parity = 0  # NOPARITY
        dcb.StopBits = 2 if float(self.stopbits) == 2 else 0  # TWOSTOPBITS / ONESTOPBIT
        dcb.Flags = 1 | ((DTR_CONTROL_ENABLE if self._dtr else DTR_CONTROL_DISABLE) << 4) | (
            (RTS_CONTROL_ENABLE if self._rts else RTS_CONTROL_DISABLE) << 12
        )

        if not kernel32.SetCommState(self._handle, ctypes.byref(dcb)):
            raise SerialException(ctypes.get_last_error(), "SetCommState failed")

        timeout_ms = max(1, int(float(self.timeout) * 1000))
        timeouts = COMMTIMEOUTS()
        timeouts.ReadIntervalTimeout = 50
        timeouts.ReadTotalTimeoutMultiplier = 0
        timeouts.ReadTotalTimeoutConstant = timeout_ms
        timeouts.WriteTotalTimeoutMultiplier = 0
        timeouts.WriteTotalTimeoutConstant = 1000
        if not kernel32.SetCommTimeouts(self._handle, ctypes.byref(timeouts)):
            raise SerialException(ctypes.get_last_error(), "SetCommTimeouts failed")

        self._escape_comm(set_dtr=self._dtr, set_rts=self._rts)
        self.reset_input_buffer()

    def _escape_comm(self, set_dtr: bool, set_rts: bool) -> None:
        if not self.is_open:
            return
        kernel32 = self._kernel32()
        SETRTS, CLRRTS = 3, 4
        SETDTR, CLRDTR = 5, 6
        kernel32.EscapeCommFunction(self._handle, SETDTR if set_dtr else CLRDTR)
        kernel32.EscapeCommFunction(self._handle, SETRTS if set_rts else CLRRTS)

    @property
    def in_waiting(self) -> int:
        if not self.is_open:
            return 0
        kernel32 = self._kernel32()

        class COMSTAT(ctypes.Structure):
            _fields_ = [("Flags", wintypes.DWORD), ("cbInQue", wintypes.DWORD), ("cbOutQue", wintypes.DWORD)]

        errors = wintypes.DWORD()
        stat = COMSTAT()
        if not kernel32.ClearCommError(self._handle, ctypes.byref(errors), ctypes.byref(stat)):
            return 0
        return int(stat.cbInQue)

    def read(self, size: int = 1) -> bytes:
        if not self.is_open:
            return b""
        size = max(1, int(size))
        kernel32 = self._kernel32()
        buf = ctypes.create_string_buffer(size)
        read_count = wintypes.DWORD(0)
        ok = kernel32.ReadFile(self._handle, buf, size, ctypes.byref(read_count), None)
        if not ok:
            raise SerialException(ctypes.get_last_error(), "ReadFile failed")
        return buf.raw[: int(read_count.value)]

    def reset_input_buffer(self) -> None:
        if not self.is_open:
            return
        kernel32 = self._kernel32()
        PURGE_RXABORT = 0x0002
        PURGE_RXCLEAR = 0x0008
        kernel32.PurgeComm(self._handle, PURGE_RXABORT | PURGE_RXCLEAR)

    def close(self) -> None:
        if self._handle is None:
            return
        try:
            kernel32 = self._kernel32()
            kernel32.CloseHandle(self._handle)
        finally:
            self._handle = None


def _reader_worker(
    cfg: dict[str, Any],
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    stop_event: threading.Event,
) -> None:
    port = str(cfg.get("port") or "COM6")
    reconnect_interval = float(cfg.get("reconnect_interval") or 5)

    while not stop_event.is_set():
        ser: _WinSerial | None = None
        try:
            ser = _WinSerial(
                port=port,
                baudrate=int(cfg.get("baudrate") or 9600),
                stopbits=float(cfg.get("stopbits") or 2),
                timeout=float(cfg.get("timeout") or 0.5),
                dtr=bool(cfg.get("dtr", False)),
                rts=bool(cfg.get("rts", True)),
            )
            ser.open()
            time.sleep(0.5)
            ser.reset_input_buffer()
            print(
                f"[IMD] Port opened: {port}, {ser.baudrate}, "
                f"stopbits={ser.stopbits}, DTR={ser.dtr}, RTS={ser.rts}"
            )
            _read_loop_like_gui(ser, cfg, loop, queue, stop_event)
        except Exception as exc:
            print(f"[IMD] Port/read error on {port}: {exc}")
            _emit(loop, queue, _offline_payload(cfg, reason=str(exc)))
            stop_event.wait(reconnect_interval)
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass


def _read_loop_like_gui(
    ser: _WinSerial,
    cfg: dict[str, Any],
    loop: asyncio.AbstractEventLoop,
    queue: asyncio.Queue,
    stop_event: threading.Event,
) -> None:
    """Packet loop copied in behavior from the working GUI read_loop()."""
    buffer = bytearray()
    last_packet_time = time.time()
    last_send_time = 0.0
    offline_sent = False
    send_interval = float(cfg.get("send_interval") or 5)
    no_signal_timeout = float(cfg.get("no_signal_timeout") or 8)
    debug_raw = bool(cfg.get("debug_raw", False))
    debug_crc = bool(cfg.get("debug_crc", False))

    while not stop_event.is_set():
        waiting = ser.in_waiting
        if waiting > 0:
            data = ser.read(waiting)
            if data:
                buffer.extend(data)
                if debug_raw:
                    preview = data[:64].hex(" ")
                    suffix = " ..." if len(data) > 64 else ""
                    print(f"[IMD RAW] +{len(data)} bytes: {preview}{suffix}")

        while len(buffer) > 0:
            packet: bytes | None = None
            mode_name = ""

            if buffer[0] == 0x05:
                if len(buffer) >= 7:
                    if debug_crc:
                        print(f"[IMD] ACK/service frame skipped: {bytes(buffer[:7]).hex(' ')}")
                    del buffer[:7]
                    continue
                break

            elif buffer[0] == 0x01 and len(buffer) >= 3:
                if buffer[1] == 0x0C and buffer[2] == 0x13:
                    if len(buffer) >= 24:
                        candidate = bytes(buffer[:24])
                        if _check_crc(candidate):
                            packet = candidate
                            mode_name = "РЕЖИМ 1 (ПУЛЬТ)"
                            del buffer[:24]
                        else:
                            if debug_crc:
                                print(f"[IMD] bad CRC 24: {candidate.hex(' ')}")
                            del buffer[0]
                            continue
                    else:
                        break
                elif buffer[1] == 0x0C and buffer[2] == 0x1B:
                    if len(buffer) >= 32:
                        candidate = bytes(buffer[:32])
                        if _check_crc(candidate):
                            packet = candidate
                            mode_name = "РЕЖИМ 2 (ВБД)"
                            del buffer[:32]
                        else:
                            if debug_crc:
                                print(f"[IMD] bad CRC 32: {candidate.hex(' ')}")
                            del buffer[0]
                            continue
                    else:
                        break
                else:
                    del buffer[0]
                    continue
            else:
                del buffer[0]
                continue

            if packet is not None:
                last_packet_time = time.time()
                offline_sent = False
                now = time.time()
                payload = _packet_to_payload(packet, mode_name, cfg)
                if now - last_send_time >= send_interval:
                    last_send_time = now
                    _emit(loop, queue, payload)
                elif debug_crc:
                    print(f"[IMD] packet OK, skipped by send_interval: {payload.get('dose_rate')}")

        if time.time() - last_packet_time > no_signal_timeout and not offline_sent:
            offline_sent = True
            _emit(loop, queue, _offline_payload(cfg, reason="Нет пакетов от ИМД"))

        time.sleep(0.05)


def _check_crc(data: bytes | bytearray) -> bool:
    if len(data) < 2:
        return False
    crc_l, crc_h = 0xFF, 0xFF
    for i in range(len(data) - 2):
        crc_l ^= data[i]
        for _ in range(8):
            l_low = crc_l & 1
            h_low = crc_h & 1
            crc_h = (crc_h >> 1) & 0xFF
            crc_l = (crc_l >> 1) & 0xFF
            crc_l = (crc_l | (h_low << 7)) & 0xFF
            if l_low == 1:
                crc_l ^= 1
                crc_h ^= 160
    return data[-2] == crc_l and data[-1] == crc_h


def _decode_val(h: int, m: int, l: int, d: int) -> tuple[float, str, float]:
    try:
        mark = h & 128
        e_h = (h & 127) + 64
        e_d = (l & 1) << 7
        e_l = (l >> 1) + ((m & 1) << 7)
        e_m = (m >> 1) + ((e_h & 1) << 7)
        e_h = (e_h >> 1) + mark
        raw_float = struct.unpack("<f", bytes([e_d, e_l, e_m, e_h]))[0]

        mult_idx = (d & 48) >> 4
        unit_idx = d & 15
        units = {0: "", 1: "%", 2: "Зв", 3: "Зв/ч", 4: "1/(с*см2)", 5: "1/(мин*см2)"}
        unit = units.get(unit_idx, "?")

        base_val = raw_float
        if mult_idx == 1:
            raw_float *= 1000.0
            unit = "м" + unit
        elif mult_idx == 2:
            raw_float *= 1000000.0
            unit = "мк" + unit
        return round(raw_float, 4), unit, base_val
    except Exception:
        return 0.0, "ошибка", 0.0


def _packet_to_payload(packet: bytes, mode_name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    is_32 = len(packet) == 32

    dr_h, dr_m, dr_l, dr_d = packet[22:26] if is_32 else packet[3:7]
    dr_val, dr_unit, pult_base_dr = _decode_val(dr_h, dr_m, dr_l, dr_d)

    err_val, _, _ = _decode_val(packet[7], packet[8], packet[9], packet[10])
    acc_val, acc_unit, pult_base_ed = _decode_val(packet[14], packet[15], packet[16], packet[17])
    imd_time = f"{packet[18]:02x}:{packet[19]:02x}:{packet[20]:02x}"

    ext_base_val = 0.0
    ext_type = "gamma"
    ext_val, ext_unit = 0.0, ""
    if is_32:
        ext_val, ext_unit, ext_base_val = _decode_val(packet[3], packet[4], packet[5], packet[6])
        vbd_byte = packet[11]
        if vbd_byte & 8:
            ext_type = "alpha"
        elif vbd_byte & 4:
            ext_type = "beta"

    err_code = packet[10]
    status_byte = packet[11]
    ext_power = (status_byte & 64) >> 6
    low_battery = (status_byte & 128) >> 7

    alarm_flags = _threshold_flags(cfg, pult_base_dr, pult_base_ed, ext_base_val, ext_type)
    status_mode = "alarm" if any(value != "-" for value in alarm_flags.values()) else "active"
    battery_level = 100 if ext_power == 1 else (10 if low_battery == 1 else 80)

    imd_power_text = "Сеть" if ext_power == 1 else ("Батарея разряжена" if low_battery == 1 else "Батарея норма")
    raw_hex = packet.hex(" ")

    return {
        "name": str(cfg.get("device_name") or "ИМД-07"),
        "online": True,
        "status": status_mode,
        "device_type": "Дозиметр ИМД-07",
        "battery_level": battery_level,
        "error_code": None if err_code == 0 else f"{err_code:02X}",
        "dose_rate": f"{dr_val} {dr_unit}",
        "error_percent": f"± {err_val:.1f} %",
        "accumulated_dose": f"{acc_val} {acc_unit}",
        "vbd_data": f"{ext_val} {ext_unit}" if ext_val > 0 else "—",
        "lat": cfg.get("lat"),
        "lon": cfg.get("lon"),

        # Дополнительные поля ИМД для панели ПОКАЗАТЕЛИ
        "imd_mode": mode_name,
        "imd_time": imd_time,
        "imd_power": imd_power_text,
        "imd_ext_type": ext_type if is_32 else "—",
        "imd_alarm_pult_dr": alarm_flags["pult_dr"],
        "imd_alarm_pult_ed": alarm_flags["pult_ed"],
        "imd_alarm_vbd": alarm_flags["vbd"],
        "imd_packet_len": len(packet),
        "imd_packet_type": "ВБД / 32 байта" if is_32 else "Пульт / 24 байта",
        "imd_crc": "OK",
        "imd_status_byte": f"0x{status_byte:02X}",
        "imd_error_byte": f"0x{err_code:02X}",
        "imd_low_battery": "Да" if low_battery else "Нет",
        "imd_external_power": "Да" if ext_power else "Нет",
        "imd_pult_dr_base": f"{pult_base_dr:.8g} Зв/ч",
        "imd_pult_ed_base": f"{pult_base_ed:.8g} Зв",
        "imd_vbd_base": f"{ext_base_val:.8g}",
        "imd_raw_packet": raw_hex,
    }


def _threshold_flags(
    cfg: dict[str, Any],
    pult_base_dr: float,
    pult_base_ed: float,
    ext_base_val: float = 0.0,
    ext_type: str = "gamma",
) -> dict[str, str]:
    thresholds = cfg.get("thresholds") or {}
    flags = {"pult_dr": "-", "pult_ed": "-", "vbd": "-"}
    try:
        if pult_base_dr > (float(thresholds.get("pult_dr", 0.500)) * 1e-6):
            flags["pult_dr"] = "превышен"
        if pult_base_ed > (float(thresholds.get("pult_ed", 5.0)) * 1e-3):
            flags["pult_ed"] = "превышен"
        if ext_base_val > 0:
            if ext_type == "gamma" and ext_base_val > (float(thresholds.get("vbd_dr", 0.500)) * 1e-6):
                flags["vbd"] = "превышен"
            elif ext_type == "beta" and ext_base_val > float(thresholds.get("vbd_beta", 0.5)):
                flags["vbd"] = "превышен"
            elif ext_type == "alpha" and ext_base_val > float(thresholds.get("vbd_alpha", 0.03)):
                flags["vbd"] = "превышен"
    except Exception as exc:
        print(f"[IMD] Threshold check error: {exc}")
    return flags


def _offline_payload(cfg: dict[str, Any], reason: str = "") -> dict[str, Any]:
    return {
        "name": str(cfg.get("device_name") or "ИМД-07"),
        "online": False,
        "status": "offline",
        "device_type": "Дозиметр ИМД-07",
        "dose_rate": "НЕТ СВЯЗИ",
        "imd_last_error": reason,
        "lat": cfg.get("lat"),
        "lon": cfg.get("lon"),
    }
