"""Upscale Idira-style DXT5nm normal maps (X in alpha, Y in green and blue, R constant) 2x.

Decodes X and Y, rebuilds Z, runs the model on the XYZ normal as an RGB image (or a plain sharpen when --sharpen is
given instead of a model), renormalises, and writes the same channel layout back so the mod can load it by name.
Inputs are PNGs of the decoded textures (see data/atlas_upscale/idira_orig_nm). Needs numpy and pillow; torch and spandrel
for --model, scipy for --sharpen.
"""
import argparse
import time
from pathlib import Path

import numpy as np
from PIL import Image

FACTOR = 2
TILE = 192
OVERLAP = 16


def decode(png: Image.Image):
    a = np.asarray(png.convert("RGBA"), dtype=np.float32)
    x = a[..., 3] / 255 * 2 - 1
    y = a[..., 1] / 255 * 2 - 1
    return x, y, a[..., 0]


def encode(x, y, red) -> Image.Image:
    length = np.sqrt(x * x + y * y)
    scale = np.where(length > 1, 1 / np.maximum(length, 1e-6), 1)
    x, y = x * scale, y * scale
    g = np.clip((y * 0.5 + 0.5) * 255, 0, 255).round().astype(np.uint8)
    a = np.clip((x * 0.5 + 0.5) * 255, 0, 255).round().astype(np.uint8)
    r = np.full(g.shape, 255, np.uint8)
    return Image.fromarray(np.dstack([r, g, g, a]), "RGBA")


def to_rgb(x, y):
    z = np.sqrt(np.clip(1 - x * x - y * y, 0, 1))
    return (np.dstack([x, y, z]) * 0.5 + 0.5).clip(0, 1)


def run_model(model, rgb):
    import torch
    dtype = torch.half if model.supports_half else torch.float32
    t = torch.from_numpy(rgb.astype(np.float32)).permute(2, 0, 1).unsqueeze(0).cuda().to(dtype)
    _, _, h, w = t.shape
    scale = model.scale
    out = torch.zeros(1, 3, h * scale, w * scale, device="cuda", dtype=torch.float16)
    step = TILE - 2 * OVERLAP
    with torch.no_grad():
        for y in range(0, h, step):
            for x in range(0, w, step):
                y0, x0 = max(y - OVERLAP, 0), max(x - OVERLAP, 0)
                y1, x1 = min(y + step + OVERLAP, h), min(x + step + OVERLAP, w)
                tile = model(t[:, :, y0:y1, x0:x1]).to(torch.float16)
                top, left = (y - y0) * scale, (x - x0) * scale
                rows, cols = min(step, h - y) * scale, min(step, w - x) * scale
                out[:, :, y * scale:y * scale + rows, x * scale:x * scale + cols] = tile[:, :, top:top + rows, left:left + cols]
    return out.clamp(0, 1).squeeze(0).permute(1, 2, 0).float().cpu().numpy()


def resize_channel(channel, size):
    return np.asarray(Image.fromarray(channel).resize(size, Image.LANCZOS))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model")
    parser.add_argument("--sharpen", type=float, help="unsharp amount on a plain 2x resize instead of a model")
    parser.add_argument("--radius", type=float, default=1.5)
    parser.add_argument("--match", default="_n.png")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model = None
    if args.model:
        from spandrel import ModelLoader
        model = ModelLoader().load_from_file(args.model).cuda().eval()
        if model.supports_half:
            model = model.half()
    for path in sorted(Path(args.source).glob("*" + args.match)):
        start = time.time()
        image = Image.open(path)
        x, y, red = decode(image)
        size = (image.width * FACTOR, image.height * FACTOR)
        if model is not None:
            result = run_model(model, to_rgb(x, y))
            if result.shape[1] != size[0]:
                result = np.asarray(Image.fromarray((result * 255).astype(np.uint8)).resize(size, Image.LANCZOS)) / 255.0
            nx = result[..., 0] * 2 - 1
            ny = result[..., 1] * 2 - 1
        else:
            nx = resize_channel(x.astype(np.float32), size)
            ny = resize_channel(y.astype(np.float32), size)
            from scipy import ndimage
            blur = lambda c: ndimage.gaussian_filter(c, args.radius)
            nx = nx + args.sharpen * (nx - blur(nx))
            ny = ny + args.sharpen * (ny - blur(ny))
        encode(nx, ny, red).save(out / path.name)
        print(f"{path.name} {image.size} -> {size} {time.time() - start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
