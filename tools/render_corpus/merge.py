#!/usr/bin/env python3
"""Merge per-machine render output into data/render/export/ (wav/<guid>.wav + index.json).

index.json entries carry "match": "guid" so the sidecar serves them on the cue guid alone (the game's
display text differs from the cleaned spoken text, so a text comparison would never match).
Hard-links the wavs when it can (the disk is tight). Never deletes; the first run directory that has a guid wins, later ones only fill gaps.

Usage: python3 tools/render_corpus/merge.py linux mac
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from jobs import take_problem  # noqa: E402


def merge(render_root: Path, names: list[str]) -> int:
    ex = render_root / "export"
    (ex / "wav").mkdir(parents=True, exist_ok=True)
    idx_path = ex / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
    for name in names:
        mpath = render_root / name / "manifest.jsonl"
        if not mpath.exists():
            continue
        for ln in mpath.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            src = render_root / name / "wav" / f"{r['guid']}.wav"
            if r["status"] != "ok" or r["guid"] in index or not src.is_file():
                continue
            if take_problem(r.get("text", ""), r.get("seconds", 0)):  # runaway/truncated take: leave a gap for a re-render
                continue
            dst = ex / "wav" / f"{r['guid']}.wav"
            if not dst.exists():
                try:
                    os.link(src, dst)  # same filesystem: no second copy of the audio
                except OSError:
                    shutil.copyfile(src, dst)
            index[r["guid"]] = {"wav": f"wav/{r['guid']}.wav", "text": r["src_text"], "match": "guid",
                                "speaker": r["speaker"], "engine": r["engine"],
                                "voice_source": r["voice_source"], "flags": r.get("flags", []),
                                **({"loudness": r["loudness"]} if r.get("loudness") else {})}
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(index)


if __name__ == "__main__":
    n = merge(ROOT / "data/render", sys.argv[1:] or ["linux", "mac"])
    print(f"{n} lines in data/render/export")
