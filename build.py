#!/usr/bin/env python3
"""Regenerate resized images and manifest.json from photos/.

Each preprocessing step lives in its own module under `preprocess/`.
To add a new step, write a function that mutates `entries` and call it here.
"""

import json

from preprocess.photos import discover
from preprocess.weather import add_weather
from preprocess.captions import add_captions
from preprocess.daynight import add_daynight


def main() -> None:
    entries = discover()
    add_weather(entries)
    add_captions(entries)
    add_daynight(entries)

    with open('manifest.json', 'w') as f:
        json.dump(entries, f, indent=2)
    print(f'Wrote manifest.json with {len(entries)} photos')


if __name__ == '__main__':
    main()
