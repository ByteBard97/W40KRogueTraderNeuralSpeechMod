#!/usr/bin/env python3
"""Capture the same pose in several texture sets and AA modes through the bridge, then crop and tile them.

  compare_sets.py OUTDIR --crop X0,Y0,X1,Y1 [--sets "plain resize,topaz_recover"] [--aa taa,off] [--zoom 0.6]
Restores TAA and the previously selected set at the end. Screenshots stay in OUTDIR (under screens/, never committed).
"""
import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import bridge  # noqa: E402

SETTLE_FRAMES = 60
STABLE_GAP_FRAMES = 15
FREEZE_FRAMES = 30
STABLE_MAX_DIFF = 6.0
STABLE_TRIES = 8


def ok(reply):
    if not reply.get("ok"):
        sys.exit(f"bridge error: {reply}")
    return reply


def stable_shot(name, box, zoom):
    """The game re-frames the character and plays a shimmer after every rebuild. Re-apply the zoom, then take shots
    until two consecutive crops agree, so every set is captured in the same settled pose."""
    import numpy as np
    previous = None
    for attempt in range(STABLE_TRIES):
        if zoom is not None:
            ok(bridge.call("zoom", value=zoom))
        ok(bridge.call("wait", frames=SETTLE_FRAMES + attempt * SETTLE_FRAMES))
        ok(bridge.call("timescale", value=0))
        ok(bridge.call("wait", frames=FREEZE_FRAMES))
        reply = ok(bridge.call("shot", name=name))
        ok(bridge.call("timescale", value=1))
        image = Image.open(bridge.to_linux(reply["path"])).convert("RGB")
        crop = image.crop(box)
        gray = np.asarray(crop.convert("L"), dtype=np.float32)
        if previous is not None and np.abs(gray - previous).mean() < STABLE_MAX_DIFF:
            return crop
        previous = gray
        ok(bridge.call("wait", frames=STABLE_GAP_FRAMES))
    sys.exit(f"pose never settled for {name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--crop", required=True)
    parser.add_argument("--sets", default="plain resize,topaz_recover,topaz_cgi,probe_stripes")
    parser.add_argument("--aa", default="taa,off")
    parser.add_argument("--zoom", type=float)
    parser.add_argument("--scale", type=float, default=1.0, help="resize crops (e.g. 2 for a 2x zoom of the pixels)")
    options = parser.parse_args()
    out = Path(options.outdir)
    out.mkdir(parents=True, exist_ok=True)
    box = tuple(int(v) for v in options.crop.split(","))
    start = ok(bridge.call("state"))
    if options.zoom is not None:
        ok(bridge.call("zoom", value=options.zoom))
        ok(bridge.call("wait", frames=SETTLE_FRAMES))
    tiles = []
    try:
        for aa in options.aa.split(","):
            ok(bridge.call("aa", mode=aa))
            ok(bridge.call("wait", frames=SETTLE_FRAMES))
            for name in options.sets.split(","):
                ok(bridge.call("texture_set", name=name))
                crop = stable_shot(f"{name.replace(' ', '_')}_{aa}", box, options.zoom)
                if options.scale != 1.0:
                    crop = crop.resize((int(crop.width * options.scale), int(crop.height * options.scale)), Image.LANCZOS)
                crop.save(out / f"{name.replace(' ', '_')}_{aa}_crop.png")
                tiles.append((f"{name} / {aa}", crop))
    finally:
        bridge.call("timescale", value=1)
        bridge.call("aa", mode="taa")
        bridge.call("texture_set", name=start.get("textureSet"))
    columns = len(options.sets.split(","))
    width, height = tiles[0][1].size
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (width * columns, height * rows))
    for i, (_, tile) in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * width, (i // columns) * height))
    sheet.save(out / "sheet.png")
    print(json.dumps({"sheet": str(out / "sheet.png"), "tiles": [label for label, _ in tiles]}, indent=2))


if __name__ == "__main__":
    main()
