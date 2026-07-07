#!/usr/bin/env python3
"""
SENTINEL — Tile Packer

Packs the on-disk XYZ tile pyramid (tiles/<style>/<z>/<x>/<y>.png — 215k+ files)
into one standard MBTiles (SQLite) container per style:

    tiles/dark/...  ->  dark.mbtiles
    tiles/sat/...   ->  sat.mbtiles

Why: 215k tiny files waste ~400 MB of NTFS cluster slack (998 MB real -> 1.4 GB
on disk) and make copy/backup crawl. One SQLite file per style removes the slack
and collapses everything to 2 files. The result is spec-compliant MBTiles, so it
also opens in QGIS / any MBTiles viewer.

MBTiles stores rows in TMS order (Y flipped vs. the XYZ/slippy scheme Leaflet and
download_tiles.py use), so we flip on the way in:  tile_row = (2**z - 1) - y

Usage:
    py -3.13 pack_tiles.py            # pack both styles, verify, keep originals
    py -3.13 pack_tiles.py --verify   # only re-verify existing .mbtiles vs folders
    py -3.13 pack_tiles.py --delete   # pack + verify, then delete source folders

Exit code is non-zero if verification finds any mismatch (safe for scripting).
"""
import argparse
import sqlite3
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TILES_DIR = ROOT / "tiles"
STYLES = ("dark", "sat")
BATCH = 4000


def _mbtiles_path(style: str) -> Path:
    return TILES_DIR / f"{style}.mbtiles"


def _iter_disk_tiles(style_dir: Path):
    """Yield (z, x, y, path) for every tiles/<style>/<z>/<x>/<y>.png on disk."""
    for z_dir in style_dir.iterdir():
        if not z_dir.is_dir() or not z_dir.name.isdigit():
            continue
        z = int(z_dir.name)
        for x_dir in z_dir.iterdir():
            if not x_dir.is_dir() or not x_dir.name.isdigit():
                continue
            x = int(x_dir.name)
            for tile in x_dir.glob("*.png"):
                if tile.stem.isdigit():
                    yield z, x, int(tile.stem), tile


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous  = OFF;
        CREATE TABLE IF NOT EXISTS metadata (name TEXT, value TEXT);
        CREATE TABLE IF NOT EXISTS tiles (
            zoom_level  INTEGER,
            tile_column INTEGER,
            tile_row    INTEGER,
            tile_data   BLOB
        );
        CREATE UNIQUE INDEX IF NOT EXISTS tile_index
            ON tiles (zoom_level, tile_column, tile_row);
        """
    )


def pack_style(style: str) -> int:
    """Pack one style folder into <style>.mbtiles. Returns tiles written."""
    style_dir = TILES_DIR / style
    if not style_dir.is_dir():
        print(f"  [{style}] no source folder, skipping")
        return 0

    out = _mbtiles_path(style)
    if out.exists():
        out.unlink()

    con = sqlite3.connect(out)
    _create_schema(con)

    zooms: set[int] = set()
    batch: list[tuple[int, int, int, bytes]] = []
    written = 0
    for z, x, y, path in _iter_disk_tiles(style_dir):
        tile_row = (1 << z) - 1 - y          # XYZ -> TMS flip
        batch.append((z, x, tile_row, path.read_bytes()))
        zooms.add(z)
        if len(batch) >= BATCH:
            con.executemany(
                "INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)", batch
            )
            written += len(batch)
            batch.clear()
            print(f"\r  [{style}] packed {written:,} tiles...", end="", flush=True)

    if batch:
        con.executemany("INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)", batch)
        written += len(batch)

    meta = {
        "name": f"SENTINEL {style}",
        "type": "baselayer",
        "version": "1.0",
        "description": f"SENTINEL offline {style} tiles",
        "format": "png",
        "scheme": "tms",
        "minzoom": str(min(zooms)) if zooms else "0",
        "maxzoom": str(max(zooms)) if zooms else "0",
    }
    con.executemany("INSERT INTO metadata VALUES (?,?)", list(meta.items()))
    con.commit()
    con.execute("VACUUM")
    con.commit()
    con.close()

    size_mb = out.stat().st_size / 1_048_576
    print(f"\r  [{style}] packed {written:,} tiles -> {out.name} ({size_mb:.1f} MB)      ")
    return written


def verify_style(style: str) -> bool:
    """Compare every on-disk tile against the MBTiles blob byte-for-byte."""
    style_dir = TILES_DIR / style
    out = _mbtiles_path(style)
    if not style_dir.is_dir():
        print(f"  [{style}] no source folder to verify against, skipping")
        return True
    if not out.exists():
        print(f"  [{style}] MISSING {out.name} — pack first")
        return False

    con = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    cur = con.cursor()

    checked = mismatches = missing = 0
    for z, x, y, path in _iter_disk_tiles(style_dir):
        tile_row = (1 << z) - 1 - y
        row = cur.execute(
            "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
            (z, x, tile_row),
        ).fetchone()
        if row is None:
            missing += 1
            if missing <= 5:
                print(f"\n  [{style}] MISSING in mbtiles: z{z}/x{x}/y{y}")
        elif row[0] != path.read_bytes():
            mismatches += 1
            if mismatches <= 5:
                print(f"\n  [{style}] BYTE MISMATCH: z{z}/x{x}/y{y}")
        checked += 1
        if checked % 5000 == 0:
            print(f"\r  [{style}] verified {checked:,}...", end="", flush=True)

    # also confirm mbtiles has no *extra* rows the folder lacks
    db_count = cur.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
    con.close()

    ok = mismatches == 0 and missing == 0 and db_count == checked
    status = "OK" if ok else "FAILED"
    print(
        f"\r  [{style}] verify {status}: {checked:,} disk tiles, "
        f"{db_count:,} in mbtiles, {mismatches} mismatched, {missing} missing        "
    )
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack SENTINEL XYZ tiles into MBTiles")
    ap.add_argument("--verify", action="store_true", help="only verify existing .mbtiles")
    ap.add_argument("--delete", action="store_true",
                    help="after successful verify, delete source tiles/<style> folders")
    args = ap.parse_args()

    print("\n  SENTINEL — Tile Packer\n")

    if not args.verify:
        print("  Packing...")
        for style in STYLES:
            pack_style(style)
        print()

    print("  Verifying (byte-for-byte)...")
    all_ok = True
    for style in STYLES:
        all_ok &= verify_style(style)
    print()

    if not all_ok:
        print("  ✗ Verification FAILED — originals left untouched.\n")
        return 1

    print("  ✓ All tiles round-trip byte-for-byte.")

    if args.delete:
        for style in STYLES:
            style_dir = TILES_DIR / style
            if style_dir.is_dir():
                shutil.rmtree(style_dir)
                print(f"  Deleted source folder tiles/{style}")
        print("\n  Done. 215k files -> 2 .mbtiles.\n")
    else:
        print("  Originals kept. Re-run with --delete to reclaim disk once satisfied.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
