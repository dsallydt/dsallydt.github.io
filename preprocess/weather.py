"""Fetch hourly weather from Open-Meteo and merge into entries."""

import datetime
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

LATITUDE = 42.36
LONGITUDE = -71.06
TIMEZONE = 'America/New_York'
TZ = ZoneInfo(TIMEZONE)
FIELDS = ('temp_f', 'code', 'wind_mph', 'wind_dir')

# WMO weather codes → human-readable labels.
# See https://open-meteo.com/en/docs (search "WMO Weather interpretation codes").
WMO = {
    0: 'Clear', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Overcast',
    45: 'Fog', 48: 'Freezing fog',
    51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
    56: 'Freezing drizzle', 57: 'Heavy freezing drizzle',
    61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
    66: 'Freezing rain', 67: 'Heavy freezing rain',
    71: 'Light snow', 73: 'Snow', 75: 'Heavy snow', 77: 'Snow grains',
    80: 'Light rain showers', 81: 'Rain showers', 82: 'Heavy rain showers',
    85: 'Light snow showers', 86: 'Snow showers',
    95: 'Thunderstorm', 96: 'Thunderstorm with hail', 99: 'Severe thunderstorm',
}
COMPASS = ('N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW')


def add_weather(entries: list[dict]) -> None:
    """Mutate `entries` in place, setting weather fields for each."""
    if not entries:
        return

    prev = _previous_weather()
    hourly = _fetch(entries[0]['date'][:10], entries[-1]['date'][:10])

    for e in entries:
        # Match in UTC: localise the photo's naive wall-clock with zoneinfo (which
        # applies the correct DST for that date) before looking it up.
        dt = datetime.datetime.fromisoformat(e['date']).replace(tzinfo=TZ)
        i = hourly['index'].get(_utc_key(dt))
        if i is not None:
            e['temp_f'] = hourly['temps'][i]
            e['code'] = hourly['codes'][i]
            e['wind_mph'] = hourly['winds'][i]
            e['wind_dir'] = hourly['wdirs'][i]
        elif e['file'] in prev:
            e.update(prev[e['file']])
        else:
            for f in FIELDS:
                e[f] = None

        display = _format(e)
        if display:
            e['weather'] = display


def _fetch_archive(start: str, end: str, params: str) -> dict:
    """Fetch from Open-Meteo's archive API and return the parsed JSON.

    `params` is the data-selection query — e.g. 'hourly=temperature_2m,...' or
    'daily=sunrise,sunset'. Raises on network/parse failure; callers fall back.
    Shared with daynight.py so the URL, curl call, and offset handling live here.
    """
    url = (
        'https://archive-api.open-meteo.com/v1/archive'
        f'?latitude={LATITUDE}&longitude={LONGITUDE}'
        f'&start_date={start}&end_date={end}'
        f'&{params}'
        f'&timezone={TIMEZONE}'
    )
    raw = subprocess.run(
        ['curl', '-fsSL', '--max-time', '30', url],
        capture_output=True, check=True,
    ).stdout
    return json.loads(raw)


def _reported_offset(data: dict) -> datetime.timezone:
    """The fixed UTC offset Open-Meteo labeled its times with.

    The archive labels every time at the offset in effect *now*, not the
    historical per-date one — re-anchor reported times to this, then convert
    with zoneinfo for the DST-correct wall-clock.
    """
    return datetime.timezone(datetime.timedelta(seconds=data['utc_offset_seconds']))


def _fetch(start: str, end: str) -> dict:
    try:
        data = _fetch_archive(
            start, end,
            'hourly=temperature_2m,weather_code,wind_speed_10m,wind_direction_10m'
            '&temperature_unit=fahrenheit&wind_speed_unit=mph')
        h = data['hourly']
        src = _reported_offset(data)
        return {
            'index': {_utc_key(datetime.datetime.fromisoformat(t).replace(tzinfo=src)): i
                      for i, t in enumerate(h['time'])},
            'temps': h['temperature_2m'],
            'codes': h['weather_code'],
            'winds': h['wind_speed_10m'],
            'wdirs': h['wind_direction_10m'],
        }
    except Exception as e:
        print(f'warning: weather fetch failed ({e}); keeping any existing weather data',
              file=sys.stderr)
        return {'index': {}, 'temps': [], 'codes': [], 'winds': [], 'wdirs': []}


def _utc_key(aware: datetime.datetime) -> str:
    """Hour-resolution UTC key, used to match a photo to its hourly weather."""
    return aware.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:00')


def _format(entry: dict) -> str:
    """Build a display string like `53°F · Overcast · 8 mph NW`."""
    if entry.get('temp_f') is None:
        return ''
    parts = [f"{round(entry['temp_f'])}°F"]
    condition = WMO.get(entry.get('code'))
    if condition:
        parts.append(condition)
    wind = _format_wind(entry.get('wind_mph'), entry.get('wind_dir'))
    if wind:
        parts.append(wind)
    return ' · '.join(parts)


def _format_wind(mph, direction) -> str:
    if mph is None:
        return ''
    speed = round(mph)
    if speed <= 3:
        return 'calm'
    if direction is None:
        return f'{speed} mph'
    return f'{speed} mph {COMPASS[round(direction / 45) % 8]}'


def _previous_weather() -> dict:
    """Load existing manifest.json weather so a failed fetch doesn't wipe data."""
    if not os.path.exists('manifest.json'):
        return {}
    try:
        with open('manifest.json') as f:
            return {
                e['file']: {field: e.get(field) for field in FIELDS}
                for e in json.load(f)
                if e.get('temp_f') is not None
            }
    except Exception:
        return {}
