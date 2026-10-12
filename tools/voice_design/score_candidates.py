#!/usr/bin/env python3
"""Score designed candidates and clone-test clips: accent (p_us, top label) and optionally UTMOS.

Run in the scorer venv:  tools/scorer/.venv-scorer/bin/python tools/voice_design/score_candidates.py [--utmos]
Scans data/voice_design/{clips,clones}/<slug>/*.wav, writes data/voice_design/scores.json keyed by
"<kind>/<slug>/<file>". Resumable: scored files are skipped. p_us above PUS_FLAG is only a hint
(the classifier called several real game actors American, see accent_calibration.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/scorer"))
sys.path.insert(0, str(Path(__file__).parent))
from accent import AccentScorer  # noqa: E402

OUT = ROOT / "data/voice_design"
PUS_FLAG = 0.5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--utmos", action="store_true")
    args = ap.parse_args()
    path = OUT / "scores.json"
    scores = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    files = sorted(p for kind in ("clips", "clones") for p in (OUT / kind).glob("*/*.wav"))
    todo = [p for p in files if f"{p.parent.parent.name}/{p.parent.name}/{p.name}" not in scores
            or (args.utmos and "utmos" not in scores[f"{p.parent.parent.name}/{p.parent.name}/{p.name}"])]
    print(f"{len(todo)} files to score of {len(files)}", flush=True)
    if not todo:
        return
    acc = AccentScorer()
    mos = None
    if args.utmos:
        from scorer import ClipScorer
        mos = ClipScorer(device="cpu", with_asr=False)
    for p in todo:
        key = f"{p.parent.parent.name}/{p.parent.name}/{p.name}"
        row = scores.get(key, {})
        row.update(acc.summary(str(p)))
        row["seconds"] = round(sf.info(str(p)).duration, 2)
        if mos is not None:
            row["utmos"] = round(float(mos.utmos(p)), 3)
        row["flag_us"] = row["p_us"] > PUS_FLAG
        scores[key] = row
        path.write_text(json.dumps(scores, indent=1), encoding="utf-8")
    print("scored", len(todo))


if __name__ == "__main__":
    main()
