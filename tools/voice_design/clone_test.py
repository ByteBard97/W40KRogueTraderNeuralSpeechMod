#!/usr/bin/env python3
"""Clone-test designed voices: render an NPC's real lines with VoxCPM2 using a candidate as the reference.

A designed clip only becomes the NPC's voice if cloning from it keeps the voice and accent, so this
renders 2 real lines per candidate. Candidates are the top --top per NPC by low p_us then UTMOS from
scores.json (or the first ones if unscored). Run in the VoxCPM2 env (Mac: ~/rt-tts/.venv-vox):
  python tools/voice_design/clone_test.py [--top 3] [--only NAME]
Output: data/voice_design/clones/<slug>/c<i>_L<j>.wav + clone_manifest.json (resumable).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))
from annotation_bridge import route  # noqa: E402
from lexicon import respell  # noqa: E402

OUT = ROOT / "data/voice_design"
CFG, TIMESTEPS = 3.0, 10


def pick_lines(jobs: list[dict], name: str, n: int = 2) -> list[dict]:
    mine = sorted((j for j in jobs if j["speaker"] == name and 80 <= len(j["text"]) <= 200), key=lambda j: j["guid"])
    if len(mine) <= n:
        return mine
    return [mine[round(i * (len(mine) - 1) / (n - 1))] for i in range(n)]  # spread across the NPC's lines


def rank(cands: list[str], slug: str, scores: dict, top: int) -> list[str]:
    def key(c):
        s = scores.get(f"clips/{slug}/{c}", {})
        return (s.get("p_us", 0.5), -s.get("utmos", 0.0))
    return sorted(cands, key=key)[:top]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    manifest = json.loads((OUT / "design_manifest.json").read_text(encoding="utf-8"))
    sp = OUT / "scores.json"
    scores = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    jobs = [json.loads(ln) for ln in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines()]
    import numpy as np
    import soundfile as sf
    from voxcpm import VoxCPM
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    cm_path = OUT / "clone_manifest.json"
    cm = json.loads(cm_path.read_text(encoding="utf-8")) if cm_path.exists() else {}
    for name, m in manifest.items():
        if args.only and name != args.only:
            continue
        lines = pick_lines(jobs, name)
        d = OUT / "clones" / m["slug"]
        d.mkdir(parents=True, exist_ok=True)
        for cand in rank(m["candidates"], m["slug"], scores, args.top):
            ref = str(OUT / "clips" / m["slug"] / cand)
            if not Path(ref).exists():
                continue
            for j, line in enumerate(lines):
                out = d / f"{Path(cand).stem}_L{j}.wav"
                if out.exists():
                    continue
                text, kw = route("voxcpm2", respell(line["text"]), line["annotation"])
                if kw.get("instruct"):
                    text = f"({kw['instruct']}){text}"
                w = model.generate(text=text, reference_wav_path=ref, cfg_value=CFG,
                                   inference_timesteps=TIMESTEPS, retry_badcase=False)
                sf.write(str(out), np.asarray(w, dtype=np.float32).reshape(-1), model.tts_model.sample_rate)
                cm[f"{m['slug']}/{out.name}"] = {"name": name, "candidate": cand, "text": line["text"]}
                cm_path.write_text(json.dumps(cm, ensure_ascii=False, indent=1), encoding="utf-8")
        print("cloned", name, flush=True)


if __name__ == "__main__":
    main()
