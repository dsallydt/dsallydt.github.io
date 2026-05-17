# Photos on the Charles

A minimalist photo site: one carousel up top, a grid below. Each caption shows date, time, and historical weather (Boston) for the moment the photo was taken.

Live at https://dsallydt.github.io/

## Adding new photos

1. Drop new photos into `photos/` (any case of `.jpg` / `.JPG`).
2. Run the build:
   ```
   ./build.sh
   ```
3. Commit and push:
   ```
   git add images/ manifest.json
   git commit -m "Add photos"
   git push
   ```

GitHub Pages picks it up automatically.

## Adding a manual caption

Some days you might want to note something special. Edit `captions.json` and add an entry keyed by filename (use `.jpg` lowercase — that's how files land after resizing):

```json
{
  "IMG_6839.jpg": "First snow of the season",
  "IMG_7392.jpg": "Crew team out at sunrise"
}
```

Re-run `./build.sh` and the caption appears below the date/weather line in italic. Photos without an entry get no caption (the default).

## What `build.sh` does

- Resizes each photo into `images/web/` (1600px, used by the carousel) and `images/thumb/` (600px, used by the grid).
- Reads each photo's EXIF creation date via `sips`.
- Fetches hourly historical weather for the full date range from [Open-Meteo](https://open-meteo.com/) (free, no API key) in a single request.
- Writes `manifest.json` with each photo's date, filename, temperature (°F), and WMO weather code, sorted chronologically.

Only new/modified photos get re-resized, so reruns are fast.

## Requirements

- macOS (uses `sips` for image resizing and EXIF dates)
- `python3` (used inside `build.sh` to fetch weather and emit JSON)
- Internet access at build time (for the weather fetch); the site itself is fully static.

## Files

- `index.html` — the entire site (HTML + CSS + JS, no build step)
- `build.sh` — regenerates `images/` and `manifest.json` from `photos/`
- `captions.json` — optional manual captions, keyed by filename
- `manifest.json` — generated; do not edit by hand
- `photos/` — original photos (gitignored)
- `images/web/`, `images/thumb/` — generated, committed

## Tweaking

- **Location**: coordinates are hardcoded in `build.sh` (`42.36, -71.06`).
- **Grid columns**: `grid-template-columns: repeat(4, 1fr)` in `index.html`.
- **Carousel size**: `max-width` on `.carousel` and `aspect-ratio` on `.stage`.
