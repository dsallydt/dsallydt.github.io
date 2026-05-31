"""Discover photos in photos/, resize them into a cache, and extract dates.

Resizing produces a high-quality intermediate in `.cache/web/` (gitignored).
The later `align.py` step is what writes the final, aligned `images/web/` and
`images/thumb/` that the site serves. Keeping the raw resize separate means a
rerun re-aligns from the untouched original, never from an already-aligned
image (which would compound the warp).
"""

import os
import re
import subprocess

PHOTOS_DIR = 'photos'
CACHE_WEB = '.cache/web'   # raw resized originals; alignment input (gitignored)
WEB_MAX = 1600
CACHE_QUALITY = 95         # high: this is re-encoded once more after warping


def discover() -> list[dict]:
    """Return chronologically-sorted entries `[{date, file}, ...]`.

    Re-resizes any photo whose cached output is missing or stale.
    """
    os.makedirs(CACHE_WEB, exist_ok=True)

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
        _ensure_resized(path, os.path.join(CACHE_WEB, out_name), WEB_MAX, CACHE_QUALITY)
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
