#!/usr/bin/env python3
"""Mix the rendered takes of each chorus cue into one group clip.

  python3 tools/render_corpus/mix_chorus.py --jobs data/render/jobs_chorus.jsonl --runs chorus --out chorus-mixed

Takes come from data/render/<run>/wav/<guid>~h<k>.wav (clean ones only: ok, no take problem, no truncated/extra-words ASR flag). A cue is mixed once
all of its voices finished. Parameters come from data/render/chorus.json (defaults plus the cue's overrides). Writes data/render/<out>/wav/<parent>.wav
and manifest.jsonl (loudness "preset": the clip is levelled here to its `speaker` target). Never overwrites a finished cue.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools/bnk_patch"))
sys.path.insert(0, str(ROOT / "tools/loudness"))

import chorus  # noqa: E402
from stitch_mixed import usable_segments  # noqa: E402
from targets import target_for  # noqa: E402
from wem import linear_gain_db, measure_levels  # noqa: E402

SR = 24000


def load(path: Path) -> np.ndarray:
    x, sr = sf.read(str(path), dtype="float32")
    x = x.mean(axis=1) if x.ndim > 1 else x
    if sr != SR:
        import librosa
        x = librosa.resample(x, orig_sr=sr, target_sr=SR)
    return x


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--spec", default=str(ROOT / "data/render/chorus.json"))
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    by_parent: dict[str, list[dict]] = defaultdict(list)
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        by_parent[j["parent"]].append(j)
    takes = usable_segments(ROOT / "data/render", a.runs)
    out = ROOT / "data/render" / a.out
    (out / "wav").mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.jsonl"
    done = {json.loads(l)["guid"] for l in mpath.read_text(encoding="utf-8").splitlines()} if mpath.exists() else set()
    mixed, waiting = 0, []
    with open(mpath, "a", encoding="utf-8") as mf:
        for parent, jobs in by_parent.items():
            if parent in done:
                continue
            jobs.sort(key=lambda j: j["seg_index"])
            if any(j["guid"] not in takes for j in jobs):
                waiting.append(parent)
                continue
            p = {**spec["defaults"], **spec["cues"].get(parent, {})}
            audio, info = chorus.mix([load(takes[j["guid"]][0]) for j in jobs], SR, jitter_ms=p["jitter_ms"],
                                     detune_cents=p["detune_cents"], reverb=p["reverb"], max_stretch=tuple(p["max_stretch"]))
            wav = out / "wav" / f"{parent}.wav"
            sf.write(str(wav), audio, SR)
            lufs, peak = measure_levels(str(wav))
            gain = linear_gain_db(lufs, peak, target_for(p["speaker"]))
            sf.write(str(wav), (audio * 10 ** (gain / 20)).astype(np.float32), SR)
            mf.write(json.dumps({"guid": parent, "speaker": p["speaker"], "engine": "voxcpm2", "text": jobs[0]["text"], "src_text": jobs[0]["src_text"],
                                 "voice_source": "chorus", "loudness": "preset", "status": "ok", "seconds": round(len(audio) / SR, 2), "flags": [],
                                 "segments": [j["guid"] for j in jobs], "mix": info}, ensure_ascii=False) + "\n")
            mixed += 1
    print(f"mixed {mixed} chorus cues into {out}; {len(waiting)} waiting on a take")


if __name__ == "__main__":
    main()
