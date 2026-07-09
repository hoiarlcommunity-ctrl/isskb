"""
Offline tile server.

Serves map tiles from per-style MBTiles (SQLite) containers — dark.mbtiles /
sat.mbtiles — packed by pack_tiles.py. Falls back to the legacy on-disk tile
pyramid (tiles/<style>/<z>/<x>/<y>.png) if a container is absent, and finally to
a generated solid-color 256×256 PNG when a tile is missing, so Leaflet always
gets a valid response without network access.

MBTiles rows are stored in TMS order (Y flipped), while Leaflet requests XYZ, so
we flip on lookup:  tile_row = (2**z - 1) - y
"""
import sqlite3
import threading
import zlib
import struct
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

router = APIRouter(tags=["tiles"])
TILES_DIR = Path(__file__).parent.parent / "tiles"

ALLOWED_STYLES = {"dark", "sat"}


# ── MBTiles readers ───────────────────────────────────────────────────────────
class _MBTiles:
    """Thread-safe read-only reader for one MBTiles file."""

    def __init__(self, path: Path):
        self._con = sqlite3.connect(f"file:{path}?mode=ro", uri=True,
                                    check_same_thread=False)
        self._lock = threading.Lock()

    def get(self, z: int, x: int, y: int) -> bytes | None:
        tile_row = (1 << z) - 1 - y          # XYZ -> TMS flip
        with self._lock:
            row = self._con.execute(
                "SELECT tile_data FROM tiles "
                "WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                (z, x, tile_row),
            ).fetchone()
        return row[0] if row else None

    def count(self) -> int:
        with self._lock:
            return self._con.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]


def _load_readers() -> dict[str, _MBTiles]:
    readers: dict[str, _MBTiles] = {}
    for style in ALLOWED_STYLES:
        mb = TILES_DIR / f"{style}.mbtiles"
        if mb.exists():
            readers[style] = _MBTiles(mb)
    return readers


_READERS = _load_readers()


# ── Solid-color PNG generator (pure stdlib, no Pillow) ────────────────────
def _solid_png(r: int, g: int, b: int, size: int = 256) -> bytes:
    """Generate a solid-color PNG with stdlib zlib/struct only."""
    row_filter = b"\x00"                    # filter type None per row
    row_data   = bytes([r, g, b]) * size    # RGB pixels
    raw        = (row_filter + row_data) * size
    compressed = zlib.compress(raw, level=9)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", compressed)
    iend = _chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


# Pre-generate fallback tiles once at import time (fast, ~200ms total)
_BLANK: dict[str, bytes] = {
    "dark": _solid_png(7,   9,  15),   # matches --bg-base
    "sat":  _solid_png(8,  12,  22),   # dark ocean-blue
}

_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


@router.get("/tiles/{style}/{z}/{x}/{y}.png")
async def get_tile(style: str, z: int, x: int, y: int) -> Response:
    if style not in ALLOWED_STYLES:
        return Response(status_code=404)

    # 1) MBTiles container (preferred)
    reader = _READERS.get(style)
    if reader is not None:
        data = reader.get(z, x, y)
        if data is not None:
            return Response(content=data, media_type="image/png",
                            headers=_CACHE_HEADERS)

    # 2) Legacy on-disk pyramid (if folders still present)
    else:
        path = TILES_DIR / style / str(z) / str(x) / f"{y}.png"
        if path.exists():
            return FileResponse(str(path), media_type="image/png",
                                headers=_CACHE_HEADERS)

    # 3) Blank fallback
    return Response(
        content=_BLANK.get(style, _BLANK["dark"]),
        media_type="image/png",
        headers=_CACHE_HEADERS,
    )


@router.get("/tiles/status")
async def tile_status():
    """Report how many tiles are available per style and the source in use."""
    result = {}
    for style in ALLOWED_STYLES:
        reader = _READERS.get(style)
        if reader is not None:
            mb = TILES_DIR / f"{style}.mbtiles"
            count = reader.count()
            size_mb = mb.stat().st_size / 1_048_576
            result[style] = {"tiles": count, "size_mb": round(size_mb, 1),
                             "ready": count > 0, "source": "mbtiles"}
        else:
            style_dir = TILES_DIR / style
            if style_dir.exists():
                count = sum(1 for _ in style_dir.rglob("*.png"))
                size_mb = sum(f.stat().st_size for f in style_dir.rglob("*.png")) / 1_048_576
                result[style] = {"tiles": count, "size_mb": round(size_mb, 1),
                                 "ready": count > 0, "source": "folder"}
            else:
                result[style] = {"tiles": 0, "size_mb": 0, "ready": False,
                                 "source": "none"}
    return result
