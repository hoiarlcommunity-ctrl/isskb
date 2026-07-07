"""
Parser for PHP print_r() output.

Input example (multi-device):
    Array
    (
        [0] => Array
            (
                [key] => sky_hunter_1
                [name] => Sky-Hunter #1
                [online] => off
                [long] => 56.307055
                [lat] => 38.188773
                [children] => Array
                    (
                    )
            )
    )

Returns: list[dict] — one dict per device.
"""

import re
from typing import Any


def parse_php_printout(text: str) -> list[dict]:
    """
    Parse PHP print_r() output and return a list of device record dicts.
    Handles both single-array (one device) and indexed-array (many devices).
    """
    tokens = _tokenize(text)
    if not tokens or tokens[0] != "__ARR__":
        return []

    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def consume():
        t = tokens[pos[0]] if pos[0] < len(tokens) else None
        pos[0] += 1
        return t

    def parse_value() -> Any:
        t = peek()
        if t == "__ARR__":
            return parse_array()
        consume()
        return t  # scalar string

    def parse_array() -> dict:
        consume()   # __ARR__
        consume()   # (
        result: dict = {}
        while peek() and peek() != ")":
            k = consume()   # e.g. '[key]' or '[0]'
            consume()       # '=>'
            v = parse_value()
            key = k[1:-1]   # strip [ ]
            result[key] = v
        consume()   # )
        return result

    top = parse_array()

    if not top:
        return []

    # Indexed array of arrays → list of devices
    if all(k.isdigit() for k in top.keys()):
        return [v for k, v in sorted(top.items(), key=lambda x: int(x[0]))
                if isinstance(v, dict)]

    # Single device dict
    return [top]


def _tokenize(text: str) -> list[str]:
    """Convert PHP print_r text into a flat token stream."""
    tokens: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "Array":
            tokens.append("__ARR__")
        elif stripped == "(":
            tokens.append("(")
        elif stripped == ")":
            tokens.append(")")
        else:
            m = re.match(r"^\[([^\]]*)\]\s*=>\s*(.*)", stripped)
            if m:
                key = m.group(1)
                val = m.group(2).strip()
                tokens.append(f"[{key}]")
                tokens.append("=>")
                if val == "Array":
                    tokens.append("__ARR__")
                elif val:
                    tokens.append(val)
    return tokens
