"""Manually align one photo by clicking matching landmarks.

You almost never need this — `build.py` aligns automatically and rescues weak
matches. But if a photo ever comes out wrong, this is how you fix it by hand:
you don't compute the matrix yourself, you click two (or more) of the SAME
landmarks in the photo and in the reference, and this solves for the transform
and writes a locked entry into align.json (which the build then never touches).

Two landmarks is the minimum — pick points far apart and easy to spot in both,
like the top of the Prudential and the top of 200 Clarendon (the Hancock tower).
More points = a more robust fit.

Usage
-----
Interactive (opens windows; click landmarks, press ENTER when done):
    .venv/bin/python preprocess/align_manual.py IMG_1234.jpg

Headless (pass the pixel pairs yourself: "photoX,photoY refX,refY; ..."):
    .venv/bin/python preprocess/align_manual.py IMG_1234.jpg \
        --points "812,540 690,560; 1190,505 1150,520"

The reference is the day reference's aligned frame, so the coordinates you click
in it ARE the shared frame coordinates every photo is mapped onto.
"""

import argparse
import os
import sys

import cv2
import numpy as np

# Allow running as a plain script (`python preprocess/align_manual.py`) from the
# project root, not just as `python -m preprocess.align_manual`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from preprocess.align import (ALIGN_JSON, CACHE_WEB, WEB_DIR, REF_DAY,
                              _decompose, _render, _load_store, _save_store)

DISPLAY_MAX = 1000  # downscale big images to fit the screen while clicking


def _solve_and_write(name, src_pts, dst_pts):
    """Fit a similarity transform from clicked pairs and lock it into align.json.

    src_pts are pixels in the photo's `.cache/web/` image; dst_pts are pixels in
    the shared frame (= the day reference's aligned image).
    """
    if len(src_pts) < 2 or len(src_pts) != len(dst_pts):
        sys.exit(f'need >=2 matched pairs, got {len(src_pts)} and {len(dst_pts)}')
    src = np.float32(src_pts).reshape(-1, 1, 2)
    dst = np.float32(dst_pts).reshape(-1, 1, 2)
    M, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    if M is None:
        sys.exit('could not fit a transform from those points — try again')
    scale, angle = _decompose(M)
    print(f'fitted: scale={scale:.4f} angle={angle:+.3f} '
          f't=({M[0, 2]:+.1f},{M[1, 2]:+.1f})')

    store = _load_store()
    store.setdefault('transforms', {})[name] = {
        'matrix': np.float32(M).tolist(), 'via': 'manual',
        'inliers': None, 'scale': round(scale, 4), 'angle': round(angle, 3),
        'locked': True,
    }
    _save_store(store)
    _render(name, M.tolist())   # write the aligned web + thumb right away
    print(f'locked {name} in {ALIGN_JSON} and re-rendered it. '
          f'It will survive future builds.')


def _click(window, img):
    """Show img (scaled to fit), collect left-clicks, return full-res points."""
    scale = min(1.0, DISPLAY_MAX / img.shape[1])
    disp = cv2.resize(img, (int(img.shape[1] * scale), int(img.shape[0] * scale)))
    pts = []

    def on_mouse(event, x, y, flags, _):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append((x / scale, y / scale))
            cv2.circle(disp, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(disp, str(len(pts)), (x + 6, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (0, 255, 0), 2)
            cv2.imshow(window, disp)

    cv2.imshow(window, disp)
    cv2.setMouseCallback(window, on_mouse)
    return pts


def _interactive(name, ref_name):
    photo = cv2.imread(os.path.join(CACHE_WEB, name))
    ref = cv2.imread(os.path.join(WEB_DIR, ref_name))
    if photo is None or ref is None:
        sys.exit('could not load photo or reference image')
    print('Click the SAME landmarks in each window, in the same order '
          '(e.g. Pru top, then Hancock top). Press ENTER when done, ESC to cancel.')
    src = _click('photo: ' + name, photo)
    dst = _click('reference frame: ' + ref_name, ref)
    while True:
        k = cv2.waitKey(0) & 0xFF
        if k in (13, 10):       # ENTER
            break
        if k == 27:             # ESC
            cv2.destroyAllWindows()
            sys.exit('cancelled')
    cv2.destroyAllWindows()
    _solve_and_write(name, src, dst)


def _parse_points(s):
    src, dst = [], []
    for pair in s.split(';'):
        a, b = pair.strip().split()
        src.append(tuple(float(v) for v in a.split(',')))
        dst.append(tuple(float(v) for v in b.split(',')))
    return src, dst


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('name', help='photo filename, e.g. IMG_1234.jpg')
    ap.add_argument('reference', nargs='?', default=REF_DAY,
                    help=f'reference frame image (default {REF_DAY})')
    ap.add_argument('--points', help='headless mode: "pX,pY rX,rY; pX,pY rX,rY"')
    args = ap.parse_args()

    if args.points:
        src, dst = _parse_points(args.points)
        _solve_and_write(args.name, src, dst)
    else:
        _interactive(args.name, args.reference)


if __name__ == '__main__':
    main()
