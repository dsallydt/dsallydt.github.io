"""Classify each photo as day or night using real sunrise/sunset times.

Fixed clock hours are wrong across seasons (a 7pm shot is dark in December but
bright in June). Instead we fetch each date's sunrise/sunset from Open-Meteo and
call it night from `NIGHT_BUFFER` after sunset until `NIGHT_BUFFER` before
sunrise. The `is_night` flag drives the site's title ("N Nights on the Charles").

Timezone note: Open-Meteo's archive returns times at a *fixed* UTC offset (the
one in effect at request time), not the historical per-date offset — so for
winter dates its "local" times are an hour off from the EST wall-clock that EXIF
timestamps use. We sidestep that by anchoring to UTC and converting with
zoneinfo, which applies the correct DST for each date.
"""

import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

from preprocess.weather import TIMEZONE, _fetch_archive, _reported_offset

TZ = ZoneInfo(TIMEZONE)
NIGHT_BUFFER = datetime.timedelta(minutes=30)  # after sunset / before sunrise

# Fallback when the sun-times fetch fails (offline): coarse fixed hours.
FALLBACK_NIGHT_START = 20
FALLBACK_NIGHT_END = 5


def add_daynight(entries: list[dict]) -> None:
    """Mutate entries in place, setting `is_night` (bool) on each."""
    if not entries:
        return
    sun = _sun_times(entries[0]['date'][:10], entries[-1]['date'][:10])
    prev = _previous_is_night()

    for e in entries:
        dt = datetime.datetime.fromisoformat(e['date'])  # naive local wall-clock
        times = sun.get(e['date'][:10])
        if times:
            sunrise, sunset = times
            e['is_night'] = dt >= sunset + NIGHT_BUFFER or dt < sunrise - NIGHT_BUFFER
        elif e['file'] in prev:
            e['is_night'] = prev[e['file']]            # fetch failed: keep prior value
        else:
            e['is_night'] = dt.hour >= FALLBACK_NIGHT_START or dt.hour < FALLBACK_NIGHT_END


def _sun_times(start: str, end: str) -> dict:
    """Return {date: (sunrise, sunset)} as naive local datetimes, or {} on failure.

    We request in local time so Open-Meteo groups sunrise/sunset by the same
    calendar date the photo's EXIF uses (avoids UTC-midnight boundary mismatches),
    then re-anchor each time to the offset Open-Meteo actually reported and
    convert with zoneinfo to the DST-correct wall-clock.
    """
    try:
        data = _fetch_archive(start, end, 'daily=sunrise,sunset')
        src = _reported_offset(data)
        daily = data['daily']
        return {date: (_to_local(sr, src), _to_local(ss, src))
                for date, sr, ss in zip(daily['time'], daily['sunrise'], daily['sunset'])}
    except Exception as e:
        print(f'warning: sunrise/sunset fetch failed ({e}); '
              f'falling back to fixed hours for day/night', file=sys.stderr)
        return {}


def _to_local(naive_iso: str, src: datetime.timezone) -> datetime.datetime:
    """Re-anchor Open-Meteo's naive local time to its reported offset, then
    convert to the DST-correct wall-clock in TZ."""
    aware = datetime.datetime.fromisoformat(naive_iso).replace(tzinfo=src)
    return aware.astimezone(TZ).replace(tzinfo=None)


def _previous_is_night() -> dict:
    """Load existing manifest.json is_night flags so a failed fetch keeps them
    (matching weather.py's behaviour, so an offline rebuild stays stable)."""
    if not os.path.exists('manifest.json'):
        return {}
    try:
        with open('manifest.json') as f:
            return {e['file']: e['is_night'] for e in json.load(f) if 'is_night' in e}
    except Exception:
        return {}
