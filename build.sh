#!/bin/bash
# Regenerate resized images and manifest.json from photos/.
# Run this whenever you add new photos. Requires macOS `sips`.

set -e
cd "$(dirname "$0")"

SRC=photos
WEB=images/web
THUMB=images/thumb
WEB_MAX=1600
THUMB_MAX=600

mkdir -p "$WEB" "$THUMB"

tmp=$(mktemp)

for f in "$SRC"/*; do
  [ -f "$f" ] || continue
  base=$(basename "$f")
  stem="${base%.*}"
  out="${stem}.jpg"

  created=$(sips -g creation "$f" 2>/dev/null | awk '/creation:/ {print $2"T"$3}')
  [ -z "$created" ] && { echo "skip (no date): $f"; continue; }
  # sips date format: 2026:05:16T17:20:10 → 2026-05-16T17:20:10
  iso=$(echo "$created" | sed 's/:/-/; s/:/-/')

  if [ ! -f "$WEB/$out" ] || [ "$f" -nt "$WEB/$out" ]; then
    sips -Z "$WEB_MAX" -s format jpeg -s formatOptions 85 "$f" --out "$WEB/$out" >/dev/null
  fi
  if [ ! -f "$THUMB/$out" ] || [ "$f" -nt "$THUMB/$out" ]; then
    sips -Z "$THUMB_MAX" -s format jpeg -s formatOptions 80 "$f" --out "$THUMB/$out" >/dev/null
  fi

  echo "$iso|$out" >> "$tmp"
done

# Sort chronologically, then fetch weather and emit manifest.json
sort "$tmp" > "$tmp.sorted"

python3 - "$tmp.sorted" <<'PY'
import json, os, sys, subprocess, datetime

entries = []
with open(sys.argv[1]) as f:
    for line in f:
        iso, file = line.rstrip('\n').split('|', 1)
        entries.append({'date': iso, 'file': file})

captions = {}
if os.path.exists('captions.json'):
    try:
        with open('captions.json') as f:
            captions = json.load(f) or {}
    except Exception as e:
        print(f'warning: could not parse captions.json ({e})', file=sys.stderr)

# Preserve existing weather so a failed fetch doesn't wipe known data.
prev_weather = {}
if os.path.exists('manifest.json'):
    try:
        with open('manifest.json') as f:
            for e in json.load(f):
                if e.get('temp_f') is not None:
                    prev_weather[e['file']] = (e.get('temp_f'), e.get('code'))
    except Exception:
        pass

# Boston, fetch hourly weather across the photo date range in one request.
start = entries[0]['date'][:10]
end = entries[-1]['date'][:10]
url = (
    'https://archive-api.open-meteo.com/v1/archive'
    f'?latitude=42.36&longitude=-71.06'
    f'&start_date={start}&end_date={end}'
    '&hourly=temperature_2m,weather_code'
    '&temperature_unit=fahrenheit'
    '&timezone=America/New_York'
)
try:
    raw = subprocess.run(
        ['curl', '-fsSL', '--max-time', '30', url],
        capture_output=True, check=True,
    ).stdout
    data = json.loads(raw)
    times = data['hourly']['time']
    temps = data['hourly']['temperature_2m']
    codes = data['hourly']['weather_code']
    index = {t: i for i, t in enumerate(times)}
except Exception as e:
    print(f'warning: weather fetch failed ({e}); keeping any existing weather data', file=sys.stderr)
    index = {}
    temps = codes = []

for e in entries:
    dt = datetime.datetime.fromisoformat(e['date'])
    key = dt.strftime('%Y-%m-%dT%H:00')
    i = index.get(key)
    if i is not None:
        e['temp_f'] = temps[i]
        e['code'] = codes[i]
    elif e['file'] in prev_weather:
        e['temp_f'], e['code'] = prev_weather[e['file']]
    else:
        e['temp_f'] = None
        e['code'] = None
    cap = captions.get(e['file'])
    if cap:
        e['caption'] = cap

missing = [f for f in captions if not any(e['file'] == f for e in entries)]
if missing:
    print(f'warning: captions.json refers to unknown files: {missing}', file=sys.stderr)

with open('manifest.json', 'w') as f:
    json.dump(entries, f, indent=2)
print(f'Wrote manifest.json with {len(entries)} photos')
PY

rm "$tmp" "$tmp.sorted"
