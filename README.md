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

- `index.html` — gallery page structure
- `about.html` — about page (edit the text inside `<main class="about">`)
- `styles.css` — styling (shared by both pages)
- `app.js` — carousel + grid behavior (loaded only on the gallery page)
- `build.py` — orchestrator; regenerates `images/` and `manifest.json` from `photos/`
- `preprocess/` — individual preprocessing modules
- `captions.json` — optional manual captions, keyed by filename
- `manifest.json` — generated; do not edit by hand
- `photos/` — original photos (gitignored)
- `images/web/`, `images/thumb/` — generated, committed

## Future ideas

Small polish to consider when ready:

- **SEO & link previews.** Add `<meta name="description">` and Open Graph tags (`og:title`, `og:image`, `og:description`) in `index.html`. These control how the site shows up in Google results and what preview card appears when the URL is shared on iMessage, Slack, Twitter, etc. Pick one favorite photo as the preview image.
- **Favicon.** The small icon in the browser tab and bookmarks. Drop a `favicon.png` (256×256 is plenty) at the project root and add `<link rel="icon" href="favicon.png">` to `<head>`.
- **Permalink to a specific photo.** Today the URL is the same no matter which photo you're viewing. Could use `#62` (or `#2026-05-16`) so you can share a particular shot.
- **Lightbox** on grid click instead of jumping to the carousel — bigger view without scrolling.
- **Sun position / golden-hour flag** in the caption — Open-Meteo has it in the same archive endpoint, so it'd be a small addition to `preprocess/weather.py` (or a new `preprocess/sun.py`).

## Tweaking

- **Location**: coordinates are at the top of `preprocess/weather.py` (`42.36, -71.06`).
- **Image sizes / quality**: at the top of `preprocess/photos.py`.
- **Grid columns**: `grid-template-columns: repeat(4, 1fr)` in `index.html`.
- **Carousel size**: `max-width` on `.carousel` and `aspect-ratio` on `.stage`.
