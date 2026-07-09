"""Minimal serial.tools.list_ports replacement for Windows."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ListPortInfo:
    device: str
    description: str = "Serial Port"
    hwid: str = ""

    @property
    def name(self) -> str:
        return self.device

    def __str__(self) -> str:
        return self.device


def comports():
    ports: list[ListPortInfo] = []
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM")
        i = 0
        while True:
            try:
                value_name, value, _ = winreg.EnumValue(key, i)
                if isinstance(value, str) and value.upper().startswith("COM"):
                    ports.append(ListPortInfo(device=value, description=value_name, hwid=value_name))
                i += 1
            except OSError:
                break
    except Exception:
        # Conservative fallback: useful when registry access is restricted.
        ports = [ListPortInfo(device=f"COM{i}") for i in range(1, 33)]

    # COM numbers should be sorted numerically: COM6 before COM12.
    def sort_key(p: ListPortInfo):
        try:
            return int(p.device.upper().replace("COM", ""))
        except Exception:
            return 9999

    return sorted(ports, key=sort_key)
