#!/usr/bin/env python3
"""Build a new export directory: a base export with the takes of one or more runs laid over it.

  python3 tools/render_corpus/overlay_export.py --base export_all_new --overlay mixed-stitched --out export_all_mixed

wavs are hard-linked (no second copy of the audio); the base export is never touched. A guid present in an overlay run replaces
the base take and its index entry (so stitched mixed cues win over the old speech-only takes); take_problem() is still applied.
The index carries `"loudness": "preset"` through for stitched cues, so patch.py leaves their level alone.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from jobs import take_problem  # noqa: E402


def link(src: Path, dst: Path) -> None:
    if dst.exists():
        if os.path.samefile(src, dst):
            return
        tmp = dst.with_name(dst.name + ".new")          # a stale link from an earlier build: swap it atomically (data stays elsewhere)
        try:
            os.link(src, tmp)
        except OSError:
            shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def usable(render_root: Path, run: str):
    """(manifest row, wav path) for every finished, clean take of a run, in manifest order."""
    for line in (render_root / run / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        src = render_root / run / "wav" / f"{r['guid']}.wav"
        if r["status"] == "ok" and src.is_file() and not take_problem(r.get("text", ""), r.get("seconds", 0)):
            yield r, src


def overlay(render_root: Path, base: str, overlays: list[str], out: str) -> tuple[int, int]:
    out_dir = render_root / out
    (out_dir / "wav").mkdir(parents=True, exist_ok=True)
    index = json.loads((render_root / base / "index.json").read_text(encoding="utf-8"))
    taken = {r["guid"]: (r, src) for run in overlays for r, src in usable(render_root, run)}   # later runs win
    for guid, e in index.items():
        if guid not in taken:                      # nothing is replaced in place: overridden guids are simply not linked
            link(render_root / base / e["wav"], out_dir / e["wav"])
    replaced = 0
    for guid, (r, src) in taken.items():
        link(src, out_dir / "wav" / f"{guid}.wav")
        replaced += guid in index
        index[guid] = {"wav": f"wav/{guid}.wav", "text": r["src_text"], "match": "guid", "speaker": r["speaker"],
                       "engine": r["engine"], "voice_source": r["voice_source"], "flags": r.get("flags", []),
                       **({"loudness": r["loudness"]} if r.get("loudness") else {})}
    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(index), replaced


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--overlay", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    n, replaced = overlay(ROOT / "data/render", a.base, a.overlay, a.out)
    print(f"{a.out}: {n} clips, {replaced} replaced from {', '.join(a.overlay)}")


if __name__ == "__main__":
    main()
