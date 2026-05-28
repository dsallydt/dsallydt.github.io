"""Discover photos in photos/, resize them, and extract creation dates."""

import os
import re
import subprocess

PHOTOS_DIR = 'photos'
WEB_DIR = 'images/web'
THUMB_DIR = 'images/thumb'
WEB_MAX = 1600
THUMB_MAX = 600
WEB_QUALITY = 85
THUMB_QUALITY = 80


def discover() -> list[dict]:
    """Return chronologically-sorted entries `[{date, file}, ...]`.

    Re-resizes any photo whose web/thumb output is missing or stale.
    """
    os.makedirs(WEB_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)

    entries = []
    for name in sorted(os.listdir(PHOTOS_DIR)):
        path = os.path.join(PHOTOS_DIR, name)
        if not os.path.isfile(path):
            continue
        date = _creation_date(path)
        if not date:
            print(f'skip (no date): {path}')
            continue
        out_name = os.path.splitext(name)[0] + '.jpg'
        _ensure_resized(path, os.path.join(WEB_DIR, out_name), WEB_MAX, WEB_QUALITY)
        _ensure_resized(path, os.path.join(THUMB_DIR, out_name), THUMB_MAX, THUMB_QUALITY)
        entries.append({'date': date, 'file': out_name})

    entries.sort(key=lambda e: e['date'])
    return entries


def _creation_date(path: str) -> str | None:
    """Read EXIF creation date via `sips`; return ISO `YYYY-MM-DDTHH:MM:SS`."""
    out = subprocess.run(
        ['sips', '-g', 'creation', path],
        capture_output=True, text=True,
    ).stdout
    m = re.search(r'creation:\s+(\S+)\s+(\S+)', out)
    if not m:
        return None
    # sips emits "2025:10:14 22:30:14" — turn the date colons into hyphens.
    return m.group(1).replace(':', '-', 2) + 'T' + m.group(2)


def _ensure_resized(src: str, dst: str, max_dim: int, quality: int) -> None:
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return
    subprocess.run(
        ['sips', '-Z', str(max_dim),
         '-s', 'format', 'jpeg',
         '-s', 'formatOptions', str(quality),
         src, '--out', dst],
        stdout=subprocess.DEVNULL, check=True,
    )
