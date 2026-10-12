#!/usr/bin/env python3
"""Apply FX Lab presets to one wav, the same way tools/fx_lab/batch.py does for the bank.

Run under tools/fx_lab/.venv-fx/bin/python (needs dawdreamer):
  fx_apply.py --in raw.wav --out fx.wav --preset "Name" [--preset "Name2"]
Presets run in series, in order. Output loudness matches the input (batch.py's rule).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import soundfile as sf

FXLAB = Path(__file__).resolve().parents[1] / "fx_lab"
sys.path.insert(0, str(FXLAB))
import batch  # noqa: E402


def apply(src: Path, dst: Path, names: list[str]) -> None:
    presets = batch.load_presets()
    missing = [n for n in names if n not in presets]
    if missing:
        raise SystemExit(f"unknown preset(s): {missing}")
    codes: dict[str, str] = {}
    steps = []
    for n in names:
        f = presets[n].get("dsp", "chain.dsp")
        codes.setdefault(f, (FXLAB / "faust" / f).read_text(encoding="utf-8"))
        steps.append({"dsp": f, "params": presets[n]["params"]})
    x, sr = sf.read(str(src), dtype="float32")
    x = x if x.ndim == 1 else x.mean(axis=1)
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), batch.process_clip(x, sr, steps, codes), sr, subtype="PCM_16")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preset", action="append", default=[])
    a = ap.parse_args()
    apply(Path(a.src), Path(a.out), a.preset)
