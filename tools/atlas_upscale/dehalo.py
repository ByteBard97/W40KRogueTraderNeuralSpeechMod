#!/usr/bin/env python3
"""Remove bright halos from an upscaled texture: clamp each pixel to the local maximum of a plain bicubic resize of the
original (plus a tolerance), and optionally the local minimum as well.

  dehalo.py ORIG.png UPSCALED.png OUT.png [--window 9] [--tol 6] [--dark]
"""
import argparse

import numpy as np
from PIL import Image
from scipy.ndimage import maximum_filter, minimum_filter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("orig"); parser.add_argument("upscaled"); parser.add_argument("out")
    parser.add_argument("--window", type=int, default=9)
    parser.add_argument("--tol", type=float, default=6)
    parser.add_argument("--dark", action="store_true", help="also clamp dark overshoot")
    options = parser.parse_args()
    up = Image.open(options.upscaled)
    base = Image.open(options.orig).convert(up.mode).resize(up.size, Image.BICUBIC)
    a, b = np.asarray(up, np.float32), np.asarray(base, np.float32)
    size = (options.window, options.window, 1)
    alpha = a[..., 3:].copy() if a.shape[-1] == 4 else None  # alpha is data (masks), never clamp it
    if alpha is not None:
        a, b = a[..., :3], b[..., :3]
    out = np.minimum(a, maximum_filter(b, size=size) + options.tol)
    if options.dark:
        out = np.maximum(out, minimum_filter(b, size=size) - options.tol)
    changed = float((np.abs(out - a) > 1).mean())
    if alpha is not None:
        out = np.concatenate([out, alpha], axis=-1)
    Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), up.mode).save(options.out)
    print("changed fraction", changed)


if __name__ == "__main__":
    main()
