#!/usr/bin/env python3
"""Assemble a self-contained folder to copy to the Mac (only clips actually needed, stdlib only).

  python3 tools/mac_pilot/build_bundle.py [--dest data/mac_pilot_bundle]

Contents: run_pilot.py, judge_logic.py, backends.py, families.py, README.md, data/{gt,pairs,answers}.json,
clips/. Copy the whole folder to the Mac; nothing there needs CUDA or the repo.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools/audio_emotion_labeling"))
from families import FAMILY_OF  # noqa: E402

CODE = ["run_pilot.py", "judge_logic.py", "backends.py"]


def ground_truth(root: Path, speaker: str = "Abelard") -> list[dict]:
    cur = json.loads((root / "data/voices/emotion_banks/curation.json").read_text(encoding="utf-8"))[speaker]
    cat = json.loads((root / "data/voices/catalog.json").read_text(encoding="utf-8"))
    gt = []
    for event, r in cur.items():
        word = r.get("emotion")
        if not word or word not in FAMILY_OF or event not in cat:
            continue
        texts = cat[event].get("texts") or []
        gt.append({"event": event, "word": word, "family": FAMILY_OF[word], "wav": cat[event]["wav"],
                   "text": texts[0]["text"] if texts else None})
    return gt


def _copy(root: Path, rel: str, dest: Path, sub: str) -> str:
    src = (root / rel) if not Path(rel).is_absolute() else Path(rel)
    name = f"{sub}/{src.name}"
    (dest / sub).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest / name)
    return name


def build_bundle(root: Path, dest: Path, code_dir: Path = HERE) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "data").mkdir(exist_ok=True)
    for f in CODE:
        shutil.copyfile(code_dir / f, dest / f)
    shutil.copyfile(root / "tools/audio_emotion_labeling/families.py", dest / "families.py")
    shutil.copyfile(code_dir / "BUNDLE_README.md", dest / "README.md")

    gt = ground_truth(root)
    for g in gt:
        g["wav"] = _copy(root, "data/voices/" + g["wav"] if not g["wav"].startswith(("/", "data/")) else g["wav"],
                         dest, "clips/real")
    (dest / "data/gt.json").write_text(json.dumps(gt, indent=1), encoding="utf-8")

    bon = root / "data/scorer_probe/best_of_n"
    pairs = json.loads((bon / "pairs.json").read_text(encoding="utf-8"))
    for p in pairs:
        for k in ("reference_wav", "a", "b"):
            p[k] = _copy(root, p[k], dest, "clips/pairs")
    (dest / "data/pairs.json").write_text(json.dumps(pairs, indent=1), encoding="utf-8")
    has_answers = (bon / "answers.json").exists()
    if has_answers:
        shutil.copyfile(bon / "answers.json", dest / "data/answers.json")
    return {"clips": len(gt), "pairs": len(pairs), "answers": has_answers}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(ROOT / "data/mac_pilot_bundle"))
    print(build_bundle(ROOT, Path(ap.parse_args().dest)))
