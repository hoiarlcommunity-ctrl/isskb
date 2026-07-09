"""
Minimal pyserial-compatible module for IMD-07 GUI on Windows.

It implements only the parts used by New_program_IMD-7/main.py:
- serial.Serial()
- serial.SerialException
- serial.STOPBITS_TWO
- serial.tools.list_ports.comports()

Drop this `serial` folder next to main.py when pip/pyserial cannot be used.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

VERSION = __version__ = "compat-nopip-1.0"

PARITY_NONE = "N"
EIGHTBITS = 8
STOPBITS_ONE = 1
STOPBITS_TWO = 2


class SerialException(OSError):
    pass


class SerialTimeoutException(SerialException):
    pass


class Serial:
    def __init__(
        self,
        port: Optional[str] = None,
        baudrate: int = 9600,
        bytesize: int = EIGHTBITS,
        parity: str = PARITY_NONE,
        stopbits: float = STOPBITS_ONE,
        timeout: Optional[float] = None,
        *args,
        **kwargs,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self._dtr = bool(kwargs.get("dtr", True))
        self._rts = bool(kwargs.get("rts", True))
        self._handle = None
        if port is not None:
            self.open()

    @property
    def is_open(self) -> bool:
        return self._handle is not None and int(self._handle.value) not in (-1, 0)

    @property
    def dtr(self) -> bool:
        return self._dtr

    @dtr.setter
    def dtr(self, value: bool) -> None:
        self._dtr = bool(value)
        if self.is_open:
            self._escape_comm(set_dtr=self._dtr, set_rts=self._rts)

    @property
    def rts(self) -> bool:
        return self._rts

    @rts.setter
    def rts(self, value: bool) -> None:
        self._rts = bool(value)
        if self.is_open:
            self._escape_comm(set_dtr=self._dtr, set_rts=self._rts)

    def open(self) -> None:
        if self.is_open:
            return
        if not self.port:
            raise SerialException("Port is not configured")
        if not hasattr(ctypes, "WinDLL"):
            raise SerialException("This no-pip serial compatibility module works only on Windows")

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
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

        handle = kernel32.CreateFileW(
            name,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            err = ctypes.get_last_error()
            raise SerialException(err, f"Не удалось открыть {self.port}")

        self._handle = wintypes.HANDLE(handle)
        try:
            self._setup_comm()
        except Exception:
            self.close()
            raise

    def _kernel32(self):
        return ctypes.WinDLL("kernel32", use_last_error=True)

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

        # Windows DCB bit fields packed into DWORD Flags:
        # fBinary bit0; fDtrControl bits4-5; fRtsControl bits12-13.
        DTR_CONTROL_DISABLE = 0
        DTR_CONTROL_ENABLE = 1
        RTS_CONTROL_DISABLE = 0
        RTS_CONTROL_ENABLE = 1

        dcb.BaudRate = int(self.baudrate)
        dcb.ByteSize = int(self.bytesize or 8)
        dcb.Parity = 0  # NOPARITY
        dcb.StopBits = 2 if float(self.stopbits) == 2 else 0  # TWOSTOPBITS / ONESTOPBIT
        dcb.Flags = 1 | ((DTR_CONTROL_ENABLE if self._dtr else DTR_CONTROL_DISABLE) << 4) | (
            (RTS_CONTROL_ENABLE if self._rts else RTS_CONTROL_DISABLE) << 12
        )

        if not kernel32.SetCommState(self._handle, ctypes.byref(dcb)):
            raise SerialException(ctypes.get_last_error(), "SetCommState failed")

        timeout_ms = max(1, int(float(self.timeout if self.timeout is not None else 0.5) * 1000))
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

    def write(self, data: bytes | bytearray) -> int:
        if not self.is_open:
            raise SerialException("Port is not open")
        raw = bytes(data)
        kernel32 = self._kernel32()
        written = wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(raw)
        ok = kernel32.WriteFile(self._handle, buf, len(raw), ctypes.byref(written), None)
        if not ok:
            raise SerialException(ctypes.get_last_error(), "WriteFile failed")
        return int(written.value)

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
