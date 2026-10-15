"""Serves the Faust compiler files (FaustWasm and libfaust) from the Studio origin.

The browser's FaustWasm loads its compiler from root-relative URLs, so the Studio page needs the same two prefixes the
FX Lab server has. The files live in tools/fx_lab/vendor and are not copied into the web build.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

VENDOR_REL = Path("tools/fx_lab/vendor")
PREFIXES = {"/faustwasm/": "faustwasm", "/libfaust-wasm/": "libfaust-wasm"}
FALLBACK_TYPE = "application/octet-stream"
CONTENT_TYPES = {
    ".wasm": "application/wasm",          # browsers refuse streaming compile of a wasm served as anything else
    ".js": "text/javascript; charset=utf-8",
    ".data": FALLBACK_TYPE,
}


def resolve(root: Path, url_path: str) -> tuple[Path, str] | None:
    """(file, content type) for a vendor URL, or None. Only a bare file name directly inside the vendor folder
    is accepted, so traversal, absolute paths and sub-folders all fall through to None."""
    for prefix, folder in PREFIXES.items():
        if not url_path.startswith(prefix):
            continue
        name = unquote(url_path[len(prefix):])
        if not name or name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
            return None
        f = root / VENDOR_REL / folder / name
        return (f, CONTENT_TYPES.get(f.suffix, FALLBACK_TYPE)) if f.is_file() else None
    return None
