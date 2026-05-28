# Photos on the Charles

A minimalist photo site: one carousel up top, a grid below. Each caption shows date, time, and historical weather (Boston) for the moment the photo was taken.

Live at https://dsallydt.github.io/

## Adding new photos

1. Drop new photos into `photos/` (any case of `.jpg` / `.JPG`).
2. Run the build:
   ```
   ./build.py
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

Re-run `./build.py` and the caption appears below the date/weather line in italic. Photos without an entry get no caption (the default).

## What `build.py` does

`build.py` is a thin orchestrator that runs each step in `preprocess/`:

- `preprocess/photos.py` — discovers photos in `photos/`, resizes each into `images/web/` (1600px, used by the carousel) and `images/thumb/` (600px, for the grid), and reads each photo's EXIF creation date via `sips`.
- `preprocess/weather.py` — fetches hourly historical weather for the full date range from [Open-Meteo](https://open-meteo.com/) (free, no API key) in a single request, and merges temperature, condition, and wind into each entry. If the fetch fails, existing weather already in `manifest.json` is preserved.
- `preprocess/captions.py` — merges entries from `captions.json` into the manifest.

The final `manifest.json` is what the page reads.

Only new/modified photos get re-resized, so reruns are fast.

### Adding a new preprocessing step

1. Write a function in a new file under `preprocess/` that takes `entries: list[dict]` and mutates it in place (or returns a new list).
2. Call it from `build.py`'s `main()`.

## Requirements

- macOS (uses `sips` for image resizing and EXIF dates)
- `python3` 3.9+
- `curl` (used to fetch weather data)
- Internet access at build time (for the weather fetch); the site itself is fully static.

## To run locally

- `python3 -m http.server 8000`
- Then open http://localhost:8000

## Files

- `index.html` — page structure
- `styles.css` — styling
- `app.js` — carousel + grid behavior
- `build.py` — orchestrator; regenerates `images/` and `manifest.json` from `photos/`
- `preprocess/` — individual preprocessing modules
- `captions.json` — optional manual captions, keyed by filename
- `manifest.json` — generated; do not edit by hand
- `photos/` — original photos (gitignored)
- `images/web/`, `images/thumb/` — generated, committed

## Tweaking

- **Location**: coordinates are at the top of `preprocess/weather.py` (`42.36, -71.06`).
- **Image sizes / quality**: at the top of `preprocess/photos.py`.
- **Grid columns**: `grid-template-columns: repeat(4, 1fr)` in `index.html`.
- **Carousel size**: `max-width` on `.carousel` and `aspect-ratio` on `.stage`.
