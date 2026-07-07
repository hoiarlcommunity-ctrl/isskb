#!/usr/bin/env python3
"""
SENTINEL — Offline Map Tile Downloader
Downloads CartoDB Dark + ESRI Satellite tiles for Russia.

Usage:
    python download_tiles.py --all
    python download_tiles.py --dark --max-zoom 9
    python download_tiles.py --sat  --max-zoom 6
    python download_tiles.py --all  --workers 8
"""
import argparse
import math
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

TILES_DIR = Path(__file__).parent / "tiles"

# Bounding boxes
RUSSIA_BBOX  = dict(west=19.3, south=41.0, east=170.0, north=81.9)
CENTRAL_BBOX = dict(west=27.0, south=47.0, east=68.0,  north=63.0)   # Central Russia + Ural
MOSCOW_EXT_BBOX = dict(west=30.0, south=51.0, east=42.0, north=57.5) # Moscow + Kaluga + Bryansk + Smolensk + Tula
KOZELSK_BBOX    = dict(west=35.0, south=53.65, east=36.5, north=54.4) # Козельский район Калужской области

SOURCES = {
    "dark": {
        "url":      "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "max_zoom": 9,
        "delay":    0.04,
        "headers": {
            "User-Agent": "SENTINEL/1.0 (offline-deployment; private)",
            "Referer":    "http://127.0.0.1:8000/",
        },
    },
    "sat": {
        "url":      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "max_zoom": 6,       # full Russia — override with --central for higher zoom
        "delay":    0.06,
        "headers": {
            "User-Agent": "SENTINEL/1.0 (offline-deployment; private)",
        },
    },
}


# ── Tile math ────────────────────────────────────────────────────────────────

def _deg2tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y_raw = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n
    return max(0, min(n - 1, x)), max(0, min(n - 1, int(y_raw)))


def _tile_range(bbox: dict, zoom: int) -> tuple[int, int, int, int]:
    """Returns (x_min, x_max, y_min, y_max) inclusive."""
    x_sw, y_sw = _deg2tile(bbox["south"], bbox["west"], zoom)
    x_ne, y_ne = _deg2tile(bbox["north"], bbox["east"], zoom)
    return min(x_sw, x_ne), max(x_sw, x_ne), min(y_sw, y_ne), max(y_sw, y_ne)


def _count_tiles(bbox: dict, max_zoom: int) -> int:
    total = 0
    for z in range(max_zoom + 1):
        x0, x1, y0, y1 = _tile_range(bbox, z)
        total += (x1 - x0 + 1) * (y1 - y0 + 1)
    return total


# ── Download worker ──────────────────────────────────────────────────────────

def _download_tile(
    style: str,
    z: int, x: int, y: int,
    url_tmpl: str,
    headers: dict,
    delay: float,
) -> str:
    out = TILES_DIR / style / str(z) / str(x) / f"{y}.png"
    if out.exists() and out.stat().st_size > 0:
        return "skip"

    url = url_tmpl.format(z=z, x=x, y=y)
    out.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            if len(data) < 64:           # empty / error tile
                return "skip"
            out.write_bytes(data)
            time.sleep(delay)
            return "ok"
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return "skip"
            wait = 2 ** attempt
        except Exception:
            wait = 2 ** attempt
        time.sleep(wait)

    return "err"


# ── Main ─────────────────────────────────────────────────────────────────────

def _download_style(style: str, max_zoom: int, workers: int, bbox: dict, label: str = "", min_zoom: int = 0):
    cfg   = SOURCES[style]
    total = sum(
        (_tile_range(bbox, z)[1]-_tile_range(bbox, z)[0]+1)*(_tile_range(bbox, z)[3]-_tile_range(bbox, z)[2]+1)
        for z in range(min_zoom, max_zoom + 1)
    )

    print(f"\n{'='*56}")
    print(f"  Style   : {style.upper()}{(' · ' + label) if label else ''}")
    print(f"  Zoom    : {min_zoom} – {max_zoom}")
    print(f"  Tiles   : ~{total:,}")
    print(f"  Workers : {workers}")
    print(f"  Output  : {TILES_DIR / style}")
    print(f"{'='*56}")
    print("  Downloading... (Ctrl+C to abort, progress saves)")
    print()

    tasks: list[tuple[int, int, int]] = []
    for z in range(min_zoom, max_zoom + 1):
        x0, x1, y0, y1 = _tile_range(bbox, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                tasks.append((z, x, y))

    done = skipped = errors = 0
    lock = Lock()
    t_start = time.monotonic()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        fmap = {
            pool.submit(
                _download_tile, style, z, x, y,
                cfg["url"], cfg["headers"], cfg["delay"]
            ): (z, x, y)
            for z, x, y in tasks
        }
        for fut in as_completed(fmap):
            res = fut.result()
            with lock:
                if   res == "ok":   done    += 1
                elif res == "skip": skipped += 1
                else:               errors  += 1
                n     = done + skipped + errors
                pct   = n / len(tasks) * 100
                eta_s = (time.monotonic() - t_start) / max(n, 1) * (len(tasks) - n)
                bar   = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                print(
                    f"\r  [{bar}] {pct:5.1f}%  "
                    f"OK:{done} Skip:{skipped} Err:{errors}  "
                    f"ETA:{int(eta_s//60)}m{int(eta_s%60):02d}s   ",
                    end="", flush=True,
                )

    elapsed = time.monotonic() - t_start
    size_mb = sum(f.stat().st_size for f in (TILES_DIR / style).rglob("*.png")) / 1_048_576
    print(f"\n\n  Completed in {elapsed:.0f}s — {done} new tiles — "
          f"{size_mb:.1f} MB on disk")


def main():
    ap = argparse.ArgumentParser(
        description="SENTINEL offline tile downloader for Russia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_tiles.py --all            # dark zoom 0-9 + sat zoom 0-6
  python download_tiles.py --dark           # dark only
  python download_tiles.py --sat            # satellite only
  python download_tiles.py --all --workers 8  # faster, more aggressive
        """,
    )
    ap.add_argument("--dark",      action="store_true", help="Download dark style")
    ap.add_argument("--sat",       action="store_true", help="Download satellite style")
    ap.add_argument("--all",       action="store_true", help="Download both styles")
    ap.add_argument("--central",   action="store_true", help="Region: Central Russia (z0-10)")
    ap.add_argument("--moscow-ext",action="store_true", help="Region: Moscow+Kaluga+Bryansk (z0-12)")
    ap.add_argument("--kozelsk",   action="store_true", help="Region: Kozelsk district, Kaluga (dark z13-16 / sat z13-15)")
    ap.add_argument("--max-zoom",  type=int, default=None, help="Override max zoom")
    ap.add_argument("--min-zoom",  type=int, default=0,    help="Start from this zoom (skip lower, default 0)")
    ap.add_argument("--workers",   type=int, default=8,    help="Parallel workers (default 8)")
    args = ap.parse_args()

    if args.all:
        args.dark = args.sat = True
    if not args.dark and not args.sat:
        ap.print_help()
        print("\nError: specify --dark, --sat, or --all")
        sys.exit(1)

    styles = [s for s, flag in [("dark", args.dark), ("sat", args.sat)] if flag]

    print("\n  SENTINEL — Offline Map Tile Downloader")

    for style in styles:
        if args.kozelsk:
            bbox     = KOZELSK_BBOX
            # dark → z16 detail, sat → z15 (z16 sat = ~3 GB)
            default_max = 16 if style == "dark" else 15
            max_zoom = args.max_zoom or default_max
            min_zoom = args.min_zoom if args.min_zoom != 0 else 13
            label    = "Козельский р-н Калужской обл."
            print(f"  Bounding box: {label} (35°E–36.5°E, 53.65°N–54.4°N)\n")
        elif args.moscow_ext:
            bbox     = MOSCOW_EXT_BBOX
            max_zoom = args.max_zoom or 12
            min_zoom = args.min_zoom
            label    = "Москва+Калуга+Брянск"
            print(f"  Bounding box: {label} (30°E–42°E, 51°N–57.5°N)\n")
        elif args.central:
            bbox     = CENTRAL_BBOX
            max_zoom = args.max_zoom or 10
            min_zoom = args.min_zoom
            label    = "Central Russia"
            print(f"  Bounding box: Central Russia (27°E–68°E, 47°N–63°N)\n")
        else:
            bbox     = RUSSIA_BBOX
            max_zoom = args.max_zoom or SOURCES[style]["max_zoom"]
            min_zoom = args.min_zoom
            label    = "Russia"
            print(f"  Bounding box: Russia (19.3°E – 170°E, 41°N – 81.9°N)\n")
        _download_style(style, max_zoom, args.workers, bbox, label, min_zoom)

    print("\n  All done. Restart SENTINEL server to use offline tiles.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Aborted. Partial download saved — resume any time.")
        sys.exit(0)
