"""Merge manual captions from captions.json into entries."""

import json
import os
import sys

CAPTIONS_FILE = 'captions.json'


def add_captions(entries: list[dict]) -> None:
    """Mutate `entries` in place, setting `caption` where defined."""
    if not os.path.exists(CAPTIONS_FILE):
        return
    try:
        with open(CAPTIONS_FILE) as f:
            captions = json.load(f) or {}
    except Exception as e:
        print(f'warning: could not parse {CAPTIONS_FILE} ({e})', file=sys.stderr)
        return

    known = {e['file'] for e in entries}
    for e in entries:
        text = captions.get(e['file'])
        if text:
            e['caption'] = text

    missing = [f for f in captions if f not in known]
    if missing:
        print(f'warning: {CAPTIONS_FILE} refers to unknown files: {missing}',
              file=sys.stderr)
