"""Align every photo onto a common skyline frame, so the gallery 'stacks'.

The idea, end to end
--------------------
Every photo is the same scene (Boston skyline over the Charles) but shot at a
different zoom, pan, height, and tilt. To make them stack we find, per photo, a
*similarity transform* (shift + rotate + uniform scale, 4 numbers) that maps it
onto a single reference frame, then warp + letterbox each into that frame.

How we find each photo's transform
----------------------------------
We detect SIFT keypoints (distinctive corners/edges), match them to a reference,
and fit the transform with RANSAC (which discards wrong matches). Matching is
*appearance* based, so it only works between photos in similar light. We handle
that with TWO references — one daytime, one night — and align each photo to
whichever it matches better.

The two references must themselves share one coordinate frame, so we link them
with a "bridge": a twilight photo that matches BOTH (it has lit windows like the
night shots and visible structure like the day shots). The day reference defines
the global frame; night photos go night-ref -> bridge -> day frame.

Anything that still won't match a reference gets a "rescue" pass against already
aligned photos of the same day/night class. Whatever remains is flagged in
align.json for a one-line manual fix (see README) rather than silently mangled.

align.json
----------
A sidecar (like captions.json) storing every photo's matrix + provenance, so the
build is deterministic and inspectable. Entries marked "locked": true are never
recomputed — that's how a manual correction sticks.
"""

import json
import os
import subprocess

import cv2
import numpy as np

CACHE_WEB = '.cache/web'      # raw resized input from photos.py
WEB_DIR = 'images/web'        # final aligned output the site serves
THUMB_DIR = 'images/thumb'
ALIGN_JSON = 'align.json'

REF_DAY = 'IMG_7744.jpg'      # clear daytime, level, full skyline -> global frame
REF_NIGHT = 'IMG_6944.jpg'    # clear night, full skyline
FRAME_W, FRAME_H = 1600, 1200

# The day reference defines a plumb frame, but the night set is placed via a
# cross-day/night "bridge" whose rotation carries a small systematic error
# (feature matching can't nail sub-degree rotation across lighting). This levels
# the whole night set onto the plumb day frame: a positive value rotates the
# night side clockwise, about the skyline centre so the skyline stays put.
NIGHT_LEVEL_ADJUST_DEG = 0.293
LEVEL_PIVOT = (800.0, 480.0)  # ~skyline centre in the frame

# A uniform rotation applied to the WHOLE stack (day + night) at output time, to
# straighten the overall frame by eye. Every photo shares the common frame (so
# they stack), but within it each photo's content is masked to the largest
# axis-aligned rectangle inside itself and the rest padded with the background
# colour — giving clean horizontal/vertical content edges (no rotation slant)
# while keeping identical output dimensions so the gallery still stacks.
GLOBAL_ROTATE_DEG = 0.2
CROP_DOWNSAMPLE = 4           # resolution divisor for the inscribed-rect search
CROP_MARGIN = 3               # downsampled px trimmed inward to avoid edge slivers

THUMB_MAX = 600
WEB_QUALITY = 88
THUMB_QUALITY = 80
BORDER_BGR = (247, 250, 250)  # = #fafaf7, the site background, so borders blend

# Matching thresholds (tuned on this set; see the prototype findings in README).
RATIO = 0.78                  # Lowe ratio test
MIN_INLIERS = 12              # below this we don't trust the fit at all
STRONG_INLIERS = 25           # at/above this a reference match is trusted as-is;
                              # below it we also try neighbours and keep the best
SCALE_RANGE = (0.4, 2.5)      # plausible zoom difference vs the reference
MAX_ANGLE = 8.0               # degrees; handheld tilt is small


# -----------------------------------------------------------------------------
# Feature detection + matching
# -----------------------------------------------------------------------------
_sift = cv2.SIFT_create(nfeatures=6000)
_bf = cv2.BFMatcher(cv2.NORM_L2)


def _skyline_mask(gray):
    """Keep the horizontal band where the city lives; drop sky + foreground.

    Sky (smooth) and rippled/icy water (busy but non-repeatable) only add false
    matches, so we restrict keypoints to the middle band that holds the skyline.
    """
    h = gray.shape[0]
    m = np.zeros_like(gray)
    m[int(0.12 * h):int(0.66 * h), :] = 255
    return m


def _features(path):
    img = cv2.imread(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return _sift.detectAndCompute(gray, _skyline_mask(gray))


def _fit(feat_src, feat_dst):
    """Return (matrix src->dst, n_inliers) or (None, 0) if not confident.

    matrix is a 2x3 similarity transform mapping src pixels onto dst pixels.
    """
    ksrc, dsrc = feat_src
    kdst, ddst = feat_dst
    if dsrc is None or ddst is None or len(dsrc) < 6 or len(ddst) < 6:
        return None, 0
    good = [m for m, n in _bf.knnMatch(dsrc, ddst, k=2) if m.distance < RATIO * n.distance]
    if len(good) < 6:
        return None, 0
    src = np.float32([ksrc[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kdst[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    M, inliers = cv2.estimateAffinePartial2D(
        src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if M is None or inliers is None:
        return None, 0
    n = int(inliers.sum())
    scale, angle = _decompose(M)
    if n < MIN_INLIERS or not (SCALE_RANGE[0] <= scale <= SCALE_RANGE[1]) or abs(angle) > MAX_ANGLE:
        return None, n
    return M, n


def _decompose(M):
    scale = float(np.hypot(M[0, 0], M[1, 0]))
    angle = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    return scale, angle


def _compose(outer, inner):
    """Return the 2x3 for: apply `inner` first, then `outer`."""
    o = np.vstack([outer, [0, 0, 1]])
    i = np.vstack([inner, [0, 0, 1]])
    return (o @ i)[:2]


def _rotate_about(pivot, deg):
    """2x3 rotation by `deg` (clockwise on screen) about a frame point."""
    th = np.radians(deg)
    c, s = np.cos(th), np.sin(th)
    px, py = pivot
    return np.float32([[c, -s, px - c * px + s * py],
                       [s, c, py - s * px - c * py]])


def _level_night(bridge):
    """Apply the night-set leveling rotation on top of the raw bridge."""
    if bridge is None or not NIGHT_LEVEL_ADJUST_DEG:
        return bridge
    return _compose(_rotate_about(LEVEL_PIVOT, NIGHT_LEVEL_ADJUST_DEG), bridge)


# -----------------------------------------------------------------------------
# Bridge: link the night reference into the day reference's frame
# -----------------------------------------------------------------------------
def _discover_bridge(feats, names):
    """Find a twilight photo matching both refs; return (bridge 2x3, source).

    bridge maps night-ref pixels into the day-ref (global) frame, computed as
    (photo->day) composed with the inverse of (photo->night).
    """
    fday, fnight = feats[REF_DAY], feats[REF_NIGHT]
    best = None  # (min_inliers, name, bridge)
    for name in names:
        if name in (REF_DAY, REF_NIGHT):
            continue
        Md, nd = _fit(feats[name], fday)
        Mn, nn = _fit(feats[name], fnight)
        if Md is None or Mn is None:
            continue
        Mn3 = np.vstack([Mn, [0, 0, 1]])
        bridge = (np.vstack([Md, [0, 0, 1]]) @ np.linalg.inv(Mn3))[:2]
        score = min(nd, nn)
        if best is None or score > best[0]:
            best = (score, name, bridge)
    if best is None:
        return None, None
    return best[2], best[1]


# -----------------------------------------------------------------------------
# Per-photo transform
# -----------------------------------------------------------------------------
def _global_transform(feats, name, bridge):
    """Transform mapping photo `name` raw pixels -> global (day-ref) frame.

    Tries the day ref directly, then the night ref via the bridge; returns the
    higher-inlier confident fit. Returns (matrix, via, inliers, scale, angle) or
    (None, None, 0, 0, 0).
    """
    Md, nd = _fit(feats[name], feats[REF_DAY])
    Mn, nn = _fit(feats[name], feats[REF_NIGHT])
    cand = []
    if Md is not None:
        cand.append((nd, Md, 'day'))
    if Mn is not None and bridge is not None:
        cand.append((nn, _compose(bridge, Mn), 'night'))
    if not cand:
        return None, None, 0, 0, 0
    n, M, via = max(cand, key=lambda c: c[0])
    s, a = _decompose(M)
    return M, via, n, s, a


def _rescue(feats, name, anchors):
    """Match a photo against well-aligned anchor photos and compose through the
    best one. Matches on visual similarity (inlier count), NOT the day/night
    clock flag — a dark winter-evening shot may match true-night photos best.

    `anchors` is {name: global_matrix}. Returns (matrix, via, n) or (None,None,0).
    """
    best = None
    for other, gM in anchors.items():
        if other == name:
            continue
        M, n = _fit(feats[name], feats[other])
        if M is None:
            continue
        if best is None or n > best[0]:
            best = (n, _compose(gM, M), other)
    if best is None:
        return None, None, 0
    return best[1], f'via:{best[2]}', best[0]


# -----------------------------------------------------------------------------
# Warp + output
# -----------------------------------------------------------------------------
def _render(name, matrix, gmat):
    """Warp the cached photo into the common frame (with the global rotation),
    mask its content to the largest axis-aligned rectangle inside itself (straight
    edges, no rotation slant), pad the rest with the background; write web+thumb.
    Output stays FRAME-sized so all photos still stack."""
    img = cv2.imread(os.path.join(CACHE_WEB, name))
    mf = np.float32(_compose(gmat, np.float32(matrix)))
    warped = cv2.warpAffine(
        img, mf, (FRAME_W, FRAME_H),
        flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
        borderValue=BORDER_BGR)
    content = cv2.warpAffine(
        np.full(img.shape[:2], 255, np.uint8), mf, (FRAME_W, FRAME_H),
        flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    x0, y0, x1, y1 = _inscribed_rect(content)
    out = np.full((FRAME_H, FRAME_W, 3), BORDER_BGR, np.uint8)
    out[y0:y1, x0:x1] = warped[y0:y1, x0:x1]
    cv2.imwrite(os.path.join(WEB_DIR, name), out,
                [cv2.IMWRITE_JPEG_QUALITY, WEB_QUALITY])
    th = cv2.resize(out, (THUMB_MAX, round(FRAME_H * THUMB_MAX / FRAME_W)),
                    interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(THUMB_DIR, name), th,
                [cv2.IMWRITE_JPEG_QUALITY, THUMB_QUALITY])


def _inscribed_rect(content):
    """Largest axis-aligned rectangle of content (255) pixels, in full-res px.

    Searched at 1/CROP_DOWNSAMPLE resolution and trimmed inward by CROP_MARGIN.
    """
    ds = CROP_DOWNSAMPLE
    small = content[::ds, ::ds] > 0
    x0, y0, x1, y1 = _largest_rect(small)
    x0, y0 = x0 + CROP_MARGIN, y0 + CROP_MARGIN
    x1, y1 = x1 - CROP_MARGIN, y1 - CROP_MARGIN
    return x0 * ds, y0 * ds, (x1 + 1) * ds, (y1 + 1) * ds


def _largest_rect(mask):
    """(x0,y0,x1,y1) inclusive of the largest all-True axis-aligned rectangle."""
    h, w = mask.shape
    heights = [0] * w
    best = (0, 0, 0, 0, 0)  # area, x0, y0, x1, y1
    for y in range(h):
        row = mask[y]
        for x in range(w):
            heights[x] = heights[x] + 1 if row[x] else 0
        stack = []  # (start_index, height)
        for x in range(w + 1):
            cur = heights[x] if x < w else 0
            start = x
            while stack and stack[-1][1] > cur:
                idx, hh = stack.pop()
                area = hh * (x - idx)
                if area > best[0]:
                    best = (area, idx, y - hh + 1, x - 1, y)
                start = idx
            stack.append((start, cur))
    return best[1], best[2], best[3], best[4]


# -----------------------------------------------------------------------------
# Orchestration
# -----------------------------------------------------------------------------
def add_alignment(entries: list[dict]) -> None:
    """Align all photos onto the common frame; set entry['aligned'] (bool).

    Mutates `entries` in place and writes aligned images + align.json. A photo's
    transform is computed once and frozen in align.json; it is only recomputed
    if missing or if its cached source is newer than align.json (so the build is
    deterministic and reruns are fast). Delete an entry to force a recompute.
    """
    os.makedirs(WEB_DIR, exist_ok=True)
    os.makedirs(THUMB_DIR, exist_ok=True)
    store = _load_store()
    prev = store.get('transforms', {})
    names = [e['file'] for e in entries
             if os.path.exists(os.path.join(CACHE_WEB, e['file']))]
    if REF_DAY not in names or REF_NIGHT not in names:
        print(f'align: SKIPPED — need both references ({REF_DAY}, {REF_NIGHT}) '
              f'in {CACHE_WEB}/')
        for e in entries:
            e['aligned'] = False
        return

    # A photo is reused (not recomputed) if it's already in align.json and its
    # cached source hasn't changed since align.json was last written.
    aj_mtime = os.path.getmtime(ALIGN_JSON) if os.path.exists(ALIGN_JSON) else 0

    def stale(name):
        src = os.path.join(CACHE_WEB, name)
        return os.path.exists(src) and os.path.getmtime(src) > aj_mtime

    # Recompute a photo only if it's new or its source changed — and NEVER if
    # it's locked (a manual fix must survive a source re-resize).
    todo = [n for n in names
            if (n not in prev or stale(n)) and not prev.get(n, {}).get('locked')]
    have_bridge = bool(store.get('bridge_night_to_day'))

    # Features are only needed when something must be (re)computed.
    feats = {}
    if todo or not have_bridge:
        print('align: detecting features...')
        feats = {n: _features(os.path.join(CACHE_WEB, n)) for n in names}

    raw_bridge, bridge_src = _bridge(store, feats, names)
    bridge = _level_night(raw_bridge)   # level the night set onto the plumb frame

    results = {}   # name -> dict(matrix, via, inliers, scale, angle[, locked])
    computed = set()

    # Reuse frozen transforms verbatim (this is the deterministic fast path).
    for name in names:
        if name not in todo:
            results[name] = prev[name]

    # Pass 1: try each photo against the day/night references.
    ref_cand = {}  # name -> (matrix or None, via, inliers)
    for name in todo:
        if name == REF_DAY:
            ref_cand[name] = (np.float32([[1, 0, 0], [0, 1, 0]]), 'reference', None)
        elif name == REF_NIGHT and bridge is not None:
            ref_cand[name] = (np.float32(bridge), 'bridge', None)
        else:
            M, via, n, _, _ = _global_transform(feats, name, bridge)
            ref_cand[name] = (M, via, n)

    # Anchors = transforms trustworthy enough to compose a rescue through: the
    # references/bridge, locked manual fixes, and any STRONG match (reused or new).
    def strong(via, n):
        return via in ('reference', 'bridge', 'manual') or (n or 0) >= STRONG_INLIERS

    anchors = {n: np.float32(r['matrix']) for n, r in results.items()
               if strong(r.get('via'), r.get('inliers'))}
    for name, (M, via, n) in ref_cand.items():
        if M is not None and strong(via, n):
            anchors[name] = np.float32(M)

    # Pass 2: finalize. A strong reference match stands as-is; a weak or missing
    # one also tries the anchors and keeps whichever fit has the most inliers
    # (this is what rescues "tweener" shots the references match only weakly).
    flagged = []
    for name in todo:
        M, via, n = ref_cand[name]
        if not strong(via, n):
            rM, rvia, rn = _rescue(feats, name, anchors)
            if rM is not None and rn > (n or 0):
                M, via, n = rM, rvia, rn
        if M is None:
            flagged.append(name)
            continue
        results[name] = _record(M, via, n)
        computed.add(name)

    # Persist (preserve locked entries verbatim; keep prior entries for photos
    # whose cache is gone so a manual fix is never lost).
    out = {'reference_day': REF_DAY, 'reference_night': REF_NIGHT,
           'frame': [FRAME_W, FRAME_H], 'bridge_source': bridge_src,
           'night_level_adjust_deg': NIGHT_LEVEL_ADJUST_DEG,
           'bridge_night_to_day': (raw_bridge.tolist() if raw_bridge is not None else None),
           'transforms': {}}
    for name in sorted(set(list(results) + list(prev))):
        if prev.get(name, {}).get('locked'):
            out['transforms'][name] = prev[name]
        elif name in results:
            out['transforms'][name] = results[name]
        elif name not in names:
            out['transforms'][name] = prev[name]

    # Output framing: a uniform global rotation applied to every photo, stored
    # separately from the per-photo transforms so it can change without
    # recomputing matches. Each photo fills the frame and is padded with the
    # background colour where it doesn't reach.
    gmat = _rotate_about(LEVEL_PIVOT, GLOBAL_ROTATE_DEG)
    out['global_rotate_deg'] = GLOBAL_ROTATE_DEG
    _save_store(out)

    # Re-render everything if the framing changed; otherwise only what's stale.
    reframed = (store.get('global_rotate_deg') != GLOBAL_ROTATE_DEG
                or store.get('night_level_adjust_deg') != NIGHT_LEVEL_ADJUST_DEG)
    rendered = 0
    for name in names:
        if name not in results:
            continue
        if reframed or name in computed or not _output_fresh(name):
            _render(name, results[name]['matrix'], gmat)
            rendered += 1

    for e in entries:
        e['aligned'] = e['file'] in results

    print(f'align: {len(results)}/{len(names)} aligned '
          f'(bridge via {bridge_src}); rendered {rendered}; '
          f'flagged {len(flagged)}'
          + (': ' + ', '.join(flagged) if flagged else ''))


def _record(M, via, inliers):
    s, a = _decompose(M)
    return dict(matrix=np.float32(M).tolist(), via=via, inliers=inliers,
                scale=round(s, 4), angle=round(a, 3))


def _bridge(store, feats, names):
    """Reuse a stored bridge if present, else discover one (needs features)."""
    if store.get('bridge_night_to_day'):
        return np.float32(store['bridge_night_to_day']), store.get('bridge_source')
    if not feats:
        return None, None
    bridge, src = _discover_bridge(feats, names)
    return (np.float32(bridge) if bridge is not None else None), src


def _output_fresh(name):
    """True if the aligned web output exists and is newer than its cache src."""
    out = os.path.join(WEB_DIR, name)
    src = os.path.join(CACHE_WEB, name)
    if not os.path.exists(out):
        return False
    return not (os.path.exists(src) and os.path.getmtime(src) > os.path.getmtime(out))


def _load_store():
    if os.path.exists(ALIGN_JSON):
        with open(ALIGN_JSON) as f:
            return json.load(f)
    return {}


def _save_store(store):
    with open(ALIGN_JSON, 'w') as f:
        json.dump(store, f, indent=2)
