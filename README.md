# Photos on the Charles

A minimalist photo site: one carousel up top, a grid below. Each caption shows date, time, and historical weather (Boston) for the moment the photo was taken.

Live at https://dsallydt.github.io/

## Adding new photos

1. Drop new photos into `photos/` (any case of `.jpg` / `.JPG`).
2. Run the build (uses the project virtualenv — see [Requirements](#requirements)):
   ```
   .venv/bin/python build.py
   ```
3. Commit and push:
   ```
   git add images/ manifest.json align.json
   git commit -m "Add photos"
   git push
   ```

GitHub Pages picks it up automatically. New photos are aligned to the existing
skyline frame automatically; the build prints how many aligned and flags any it
couldn't (see [Aligning photos](#aligning-photos)).

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

- `preprocess/photos.py` — discovers photos in `photos/`, resizes each into a high-quality intermediate in `.cache/web/` (1600px, gitignored), and reads each photo's EXIF creation date via `sips`.
- `preprocess/weather.py` — fetches hourly historical weather for the full date range from [Open-Meteo](https://open-meteo.com/) (free, no API key) in a single request, and merges temperature, condition, and wind into each entry. If the fetch fails, existing weather already in `manifest.json` is preserved.
- `preprocess/captions.py` — merges entries from `captions.json` into the manifest.
- `preprocess/daynight.py` — flags each photo day or night using that date's real sunrise/sunset from Open-Meteo (night = 30 min after sunset to 30 min before sunrise). This drives the site title ("N Nights on the Charles").
- `preprocess/align.py` — aligns every photo onto a common skyline frame and writes the final `images/web/` (1600px, carousel) and `images/thumb/` (600px, grid) that the site serves. See [Aligning photos](#aligning-photos).

The final `manifest.json` is what the page reads.

Only new/modified photos get re-resized and re-aligned, so reruns are fast.

### Adding a new preprocessing step

1. Write a function in a new file under `preprocess/` that takes `entries: list[dict]` and mutates it in place (or returns a new list).
2. Call it from `build.py`'s `main()`.

## Aligning photos

Every photo is the same view (the Boston skyline over the Charles) but shot at a
different zoom, pan, height, and tilt. `align.py` finds, per photo, a *similarity
transform* (shift + rotate + uniform scale) that maps it onto one shared frame,
warps each photo into that frame, straightens it, and pads with the background
colour as needed — so the skyline lands in the same place in every shot and the
gallery "stacks."

**How it finds each transform.** It detects SIFT keypoints (distinctive
corners/edges), matches them to a reference photo, and fits the transform with
RANSAC (which discards bad matches). Matching is appearance-based, so it only
works between photos in *similar* light — a sunlit building and the same building
at night don't look alike to the matcher. So there are **two references**, one
day (`IMG_7744.jpg`) and one night (`IMG_6944.jpg`), and each photo aligns to
whichever it matches better.

The two references share one coordinate frame via a **bridge**: a twilight photo
that matches *both* (lit windows like the night shots, visible structure like the
day shots) links them automatically. The day reference defines the global frame.

If a photo matches the references only *weakly* (or not at all) — common for
"tweener" shots like a dark winter evening that's neither clearly day nor night —
a **rescue pass** matches it against the already well-aligned photos and keeps
whichever fit has the most inliers, composing through that neighbour. This is by
visual similarity, not the clock, so a dark-evening photo can align via the
true-night shots it actually resembles.

**Leveling & framing (output stage).** Feature matching can't nail sub-degree
rotation across day/night, so two knobs at the top of `align.py` clean up the
result by eye: `NIGHT_LEVEL_ADJUST_DEG` rotates the whole night set onto the
plumb day frame (the bridge leaves it ~0.3° off), and `GLOBAL_ROTATE_DEG` rotates
the entire stack uniformly to straighten the overall frame. After warping, each
photo's content is masked to the largest axis-aligned rectangle inside itself
(so its edges are horizontal/vertical, not slanted by the rotation) and the rest
padded with the background colour — all on the same frame, so the stack is kept.
To re-tune, change a knob and delete `align.json` (or the output images).

**`align.json`** records every photo's transform and how it was derived (`via`),
plus the discovered bridge and the framing knobs. Like `captions.json`, it's the
source of truth: a transform is computed once and frozen, so the build is
deterministic and reruns are fast. Delete a photo's entry to force a recompute;
delete the whole file to recompute everything.

**If a photo still comes out misaligned.** Run the manual helper — you don't
compute any matrix yourself, you just click the same two (or more) landmarks in
the photo and in the reference (e.g. the tops of the Prudential and 200
Clarendon), and it solves for the transform and locks it in:

```
.venv/bin/python preprocess/align_manual.py IMG_1234.jpg
```

Pick landmarks far apart and easy to spot in both; more points give a sturdier
fit. This writes a `"locked": true` entry into `align.json` and re-renders that
photo immediately. Locked entries are never recomputed, so the fix survives every
future build. (You can also hand-edit a locked entry's matrix in `align.json` if
you ever need to, but clicking is far easier.)

## Requirements

- macOS (uses `sips` for image resizing and EXIF dates)
- `python3` 3.9+
- [`uv`](https://docs.astral.sh/uv/) for the Python environment. One-time setup:
  ```
  uv venv
  uv pip install -r requirements.txt   # opencv-python + numpy, for align.py
  ```
  Then run the build with the venv's Python: `.venv/bin/python build.py`.
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
- `preprocess/align_manual.py` — helper to hand-fix one photo's alignment by clicking landmarks (see [Aligning photos](#aligning-photos))
- `captions.json` — optional manual captions, keyed by filename
- `align.json` — generated; per-photo alignment transforms (editable to fix or lock a photo — see [Aligning photos](#aligning-photos))
- `manifest.json` — generated; do not edit by hand
- `requirements.txt` — Python deps for the build (`opencv-python`, `numpy`)
- `photos/` — original photos (gitignored)
- `.cache/web/` — resized originals, alignment input (gitignored)
- `images/web/`, `images/thumb/` — generated (aligned), committed

## Future ideas

Small polish to consider when ready:

- **SEO & link previews.** Add `<meta name="description">` and Open Graph tags (`og:title`, `og:image`, `og:description`) in `index.html`. These control how the site shows up in Google results and what preview card appears when the URL is shared on iMessage, Slack, Twitter, etc. Pick one favorite photo as the preview image.
- **Favicon.** The small icon in the browser tab and bookmarks. Drop a `favicon.png` (256×256 is plenty) at the project root and add `<link rel="icon" href="favicon.png">` to `<head>`.
- **Permalink to a specific photo.** Today the URL is the same no matter which photo you're viewing. Could use `#62` (or `#2026-05-16`) so you can share a particular shot.
- **Lightbox** on grid click instead of jumping to the carousel — bigger view without scrolling.

## Tweaking

- **Location**: coordinates are at the top of `preprocess/weather.py` (`42.36, -71.06`); `daynight.py` reuses them.
- **Day/night cutoff**: `NIGHT_BUFFER` at the top of `preprocess/daynight.py` (default 30 min past sunset / before sunrise).
- **Image sizes / quality**: at the top of `preprocess/photos.py` and `preprocess/align.py`.
- **Alignment**: references, frame size, background/letterbox color, matching thresholds, and the leveling/rotation knobs (`NIGHT_LEVEL_ADJUST_DEG`, `GLOBAL_ROTATE_DEG`) are constants at the top of `preprocess/align.py`. After changing any of them, delete `align.json` (or just the output images for the framing knobs) and rebuild. To re-pick a reference, set `REF_DAY`/`REF_NIGHT` and delete `align.json`.
- **Grid columns**: `grid-template-columns: repeat(4, 1fr)` in `index.html`.
- **Carousel size**: `max-width` on `.carousel` and `aspect-ratio` on `.stage`.
