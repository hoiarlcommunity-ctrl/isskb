"""Tiny requests.post compatibility shim for the IMD GUI.

Only implements the call used in main.py:
    requests.post(url, json=[payload], timeout=10)
"""
from __future__ import annotations

import json as _json
import urllib.error
import urllib.request


class Response:
    def __init__(self, status_code: int, text: str):
        self.status_code = int(status_code)
        self.text = text
        self.content = text.encode("utf-8", errors="replace")

    def json(self):
        return _json.loads(self.text)


def post(url, json=None, timeout=None, headers=None):
    body = b"" if json is None else _json.dumps(json, ensure_ascii=False).encode("utf-8")
    req_headers = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, method="POST", headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return Response(getattr(resp, "status", resp.getcode()), raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return Response(exc.code, raw.decode("utf-8", errors="replace"))
