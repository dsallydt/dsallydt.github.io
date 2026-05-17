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

# Sort chronologically, emit manifest.json
sort "$tmp" > "$tmp.sorted"

{
  echo "["
  first=1
  while IFS='|' read -r iso file; do
    [ $first -eq 1 ] && first=0 || echo ","
    printf '  {"date": "%s", "file": "%s"}' "$iso" "$file"
  done < "$tmp.sorted"
  echo ""
  echo "]"
} > manifest.json

rm "$tmp" "$tmp.sorted"
count=$(grep -c '"file"' manifest.json)
echo "Wrote manifest.json with $count photos"
