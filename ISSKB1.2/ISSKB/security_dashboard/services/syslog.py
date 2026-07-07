"""
In-memory ring buffer for system event logs.
Stores last MAX_ENTRIES events; exposed via /api/admin/logs.
"""
import time
from collections import deque
from datetime import datetime, timezone

MAX_ENTRIES = 500

_log: deque = deque(maxlen=MAX_ENTRIES)
_seq = 0


def add(level: str, category: str, message: str, detail: str | None = None) -> None:
    """
    level:    "info" | "warn" | "error" | "debug"
    category: "poller" | "heartbeat" | "sync" | "api" | "ws" | "system"
    """
    global _seq
    _seq += 1
    _log.appendleft({
        "id":       _seq,
        "ts":       datetime.now(timezone.utc).isoformat(),
        "level":    level,
        "category": category,
        "message":  message,
        "detail":   detail,
    })


def get(limit: int = 200, category: str | None = None, level: str | None = None) -> list[dict]:
    items = list(_log)
    if category:
        items = [e for e in items if e["category"] == category]
    if level:
        items = [e for e in items if e["level"] == level]
    return items[:limit]
