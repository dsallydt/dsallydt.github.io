"""Classify each photo as day or night based on its local timestamp."""

import datetime

NIGHT_START_HOUR = 20  # 8 PM, inclusive
NIGHT_END_HOUR = 5     # 5 AM, exclusive (so 5:00 AM counts as day)


def add_daynight(entries: list[dict]) -> None:
    """Mutate entries in place, setting `is_night` (bool) on each."""
    for e in entries:
        hour = datetime.datetime.fromisoformat(e['date']).hour
        e['is_night'] = hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR
