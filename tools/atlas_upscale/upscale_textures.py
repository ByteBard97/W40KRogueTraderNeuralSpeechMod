"""Upscale character diffuse textures from the user's own game install into the mod's Textures folder.

Reads textures out of a Unity bundle, fills the black gaps between UV islands, runs a neural 2x model on RGB,
upscales alpha separately, and writes <textureName>.png. Normal and mask maps are not handled here: the mod
resizes those itself.

Run with an environment that has torch (CUDA), spandrel, UnityPy, scipy, pillow and numpy.
"""
import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
import UnityPy
from PIL import Image
from scipy import ndimage
from spandrel import ModelLoader

FACTOR = 2
TILE = 256
OVERLAP = 32
TEXTURE_SUFFIX = "_d"


def fill_unused(rgb: np.ndarray) -> np.ndarray:
    """Copy the nearest island colour into pure-black gaps so the model does not bleed black into islands."""
    unused = rgb.sum(axis=2) == 0
    if not unused.any():
        return rgb
    nearest = ndimage.distance_transform_edt(unused, return_distances=False, return_indices=True)
    return rgb[nearest[0], nearest[1]]


@torch.no_grad()
def run_tiled(model, rgb: np.ndarray) -> np.ndarray:
    scale = model.scale
    dtype = torch.half if model.supports_half else torch.float32
    x = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float().div(255).cuda().to(dtype)
    _, _, height, width = x.shape
    out = torch.zeros(1, 3, height * scale, width * scale, device="cuda", dtype=torch.float16)
    step = TILE - 2 * OVERLAP
    for y in range(0, height, step):
        for xx in range(0, width, step):
            y0, x0 = max(y - OVERLAP, 0), max(xx - OVERLAP, 0)
            y1, x1 = min(y + step + OVERLAP, height), min(xx + step + OVERLAP, width)
            tile = model(x[:, :, y0:y1, x0:x1]).to(torch.float16)
            top, left = (y - y0) * scale, (xx - x0) * scale
            rows, cols = min(step, height - y) * scale, min(step, width - xx) * scale
            out[:, :, y * scale:y * scale + rows, xx * scale:xx * scale + cols] = tile[:, :, top:top + rows, left:left + cols]
    return (out.clamp(0, 1) * 255).round().byte().squeeze(0).permute(1, 2, 0).cpu().numpy()


def upscale(model, image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    rgb = np.array(rgba)[:, :, :3]
    result = run_tiled(model, fill_unused(rgb))
    size = (rgba.width * FACTOR, rgba.height * FACTOR)
    if result.shape[1] != size[0]:
        result = np.array(Image.fromarray(result).resize(size, Image.LANCZOS))
    alpha = rgba.getchannel("A").resize(size, Image.LANCZOS)
    out = Image.fromarray(result).convert("RGBA")
    out.putalpha(alpha)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bundle", required=True, help="path to a Unity bundle, e.g. Bundles/equipment")
    parser.add_argument("--model", required=True, help="path to the upscaler weights (.pth or .safetensors)")
    parser.add_argument("--out", required=True, help="output folder, usually the mod's Textures folder")
    parser.add_argument("--match", required=True, help="regex matched against texture names")
    parser.add_argument("--exclude", default=None, help="regex for names to skip")
    args = parser.parse_args()

    model = ModelLoader().load_from_file(args.model).cuda().eval()
    if model.supports_half:
        model = model.half()
    pattern = re.compile(args.match)
    skip = re.compile(args.exclude) if args.exclude else None
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    done = 0
    seen = set()
    for obj in UnityPy.load(args.bundle).objects:
        if obj.type.name != "Texture2D":
            continue
        tex = obj.read()
        name = tex.m_Name
        if name in seen or not name.endswith(TEXTURE_SUFFIX) or not pattern.search(name) or (skip and skip.search(name)):
            continue
        seen.add(name)
        started = time.time()
        upscale(model, tex.image).save(out_dir / f"{name}.png")
        done += 1
        print(f"{name} {tex.m_Width}x{tex.m_Height} -> {tex.m_Width * FACTOR}x{tex.m_Height * FACTOR} ({time.time() - started:.1f}s)", flush=True)
    print(f"wrote {done} textures to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
