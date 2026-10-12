#!/usr/bin/env python3
"""Test render of mixed cues (speech plus narration): each segment in its own voice, stitched into one take.

Speech segments use the speaker's reference clip and the cue's annotation; narration segments use the BG3 narrator
reference. Audio comes from the VoxCPM2 live backend (tools/voice_design/live_backend.py, default localhost:8909, which
is the Windows 4070 through an ssh tunnel). Writes data/render/mixed_test/ with the stitched wavs, the installed
speech-only take for comparison, and a listening page.

  /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/render_corpus/mixed_render.py [--n 30] [--backend http://localhost:8909]
  cd data/render/mixed_test && python3 -m http.server 8911
"""
from __future__ import annotations

import argparse
import base64
import json
import random
import shutil
import sys
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))

from annotation_bridge import route  # noqa: E402
from jobs import take_problem  # noqa: E402
from mixed import NARRATION, SPEECH, segments  # noqa: E402
from plan import _narrator_ref  # noqa: E402
from render import CFG, TIMESTEPS, pronounce  # noqa: E402
from stitch import stitch  # noqa: E402

OUT = ROOT / "data/render/mixed_test"
EXPORT = ROOT / "data/render/export_all_new"
MAX_CHARS = 450
VOICED_SOURCES = {"emotion_bank", "prompt_bank"}
PATTERNS = ("speech>narration", "narration>speech", "speech>narration>speech", "other")


def pattern(segs: list[tuple[str, str]]) -> str:
    kinds = ">".join(k for k, _ in segs)
    return kinds if kinds in PATTERNS else "other"


def pick(n: int, seed: int) -> list[dict]:
    index = json.loads((EXPORT / "index.json").read_text(encoding="utf-8"))
    by_pattern: dict[str, list[dict]] = {p: [] for p in PATTERNS}
    for line in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        if job["speaker"] == "narrator" or job["voice_source"] not in VOICED_SOURCES or job["guid"] not in index:
            continue
        segs = segments(job["src_text"])
        if {k for k, _ in segs} != {SPEECH, NARRATION} or len(job["src_text"]) > MAX_CHARS:
            continue
        by_pattern[pattern([(k.replace("speech", "speech"), t) for k, t in segs])].append({**job, "segments": segs})
    rng = random.Random(seed)
    chosen: list[dict] = []
    quota = {"speech>narration": 0.3, "narration>speech": 0.4, "speech>narration>speech": 0.2, "other": 0.1}
    for p, share in quota.items():
        pool = by_pattern[p]
        rng.shuffle(pool)
        chosen += pool[: max(1, round(n * share))]
    return chosen[:n]


def generate(backend: str, text: str, ref_path: Path, annotation) -> tuple[np.ndarray, int]:
    text, kw = route("voxcpm2", pronounce(text, "voxcpm2"), annotation)
    body = {"text": text, "instruct": kw.get("instruct") or "", "cfg": CFG, "timesteps": TIMESTEPS, "return_audio": True,
            "reference_wav": "(sent)", "reference_b64": base64.b64encode(ref_path.read_bytes()).decode()}
    req = urllib.request.Request(backend + "/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=600).read())
    if "error" in out:
        raise RuntimeError(out["error"])
    tmp = OUT / "_tmp.wav"
    tmp.write_bytes(base64.b64decode(out["audio_b64"]))
    wav, sr = sf.read(str(tmp), dtype="float32")
    return np.asarray(wav, dtype=np.float32).reshape(-1), sr


def render_segment(backend: str | None, kind: str, text: str, job: dict, narrator: dict, synth=None):
    ref = job["ref"] if kind == SPEECH else narrator
    annotation = job["annotation"] if kind == SPEECH else None
    for _attempt in range(2):
        if synth is not None:  # local GPU, same call path as render.render_take
            wav, sr = synth(pronounce(text, "voxcpm2"), {"wav": str(ROOT / ref["wav"]), "text": ref["text"]}, annotation)
        else:
            wav, sr = generate(backend, text, ROOT / ref["wav"], annotation)
        if take_problem(text, len(wav) / sr) is None:
            break
    return wav, sr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--backend", default="http://localhost:8909")
    ap.add_argument("--local", action="store_true", help="load VoxCPM2 in this process (local GPU) instead of calling the backend")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    narrator = _narrator_ref()
    synth = None
    if args.local:
        from render import load_engine
        synth = load_engine("voxcpm2")
    manifest = []
    items = pick(args.n, args.seed)
    print(f"{len(items)} mixed cues", flush=True)
    for i, job in enumerate(items, 1):
        pieces, sr = [], 24000
        for kind, text in job["segments"]:
            wav, sr = render_segment(args.backend, kind, text, job, narrator, synth)
            pieces.append(wav)
        g = job["guid"]
        sf.write(str(OUT / f"{g}_stitched.wav"), stitch(pieces, sr), sr)
        shutil.copy(EXPORT / "wav" / f"{g}.wav", OUT / f"{g}_current.wav")
        manifest.append({"guid": g, "speaker": job["speaker"], "pattern": pattern(job["segments"]),
                         "segments": [{"kind": k, "text": t} for k, t in job["segments"]]})
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"{i}/{len(items)} {g} {job['speaker']} {pattern(job['segments'])}", flush=True)
    (OUT / "index.html").write_text(PAGE, encoding="utf-8")
    print(f"page: {OUT}/index.html (serve with http.server)")


PAGE = """<!doctype html><meta charset=utf-8><title>Mixed cues</title>
<style>body{font:15px system-ui;max-width:820px;margin:20px auto;padding:0 16px;background:#161616;color:#ddd}
.p{border:1px solid #333;border-radius:8px;padding:12px;margin:14px 0}.s{margin:2px 0}.n{color:#c9a96e;font-style:italic}.k{color:#999}
audio{width:100%;margin:4px 0}</style>
<h2>Mixed cues: current (speech only) vs stitched (speech + narrator)</h2><div id=l></div>
<script>fetch('manifest.json').then(r=>r.json()).then(m=>{l.innerHTML=m.map((p,i)=>`<div class=p><b>${i+1}</b> ${p.speaker} <span class=k>${p.pattern}</span>
${p.segments.map(s=>`<div class="s ${s.kind=='narration'?'n':''}">${s.kind=='narration'?'[narrator] ':''}${s.text}</div>`).join('')}
<div>current <audio controls preload=none src="${p.guid}_current.wav"></audio></div>
<div>stitched <audio controls preload=none src="${p.guid}_stitched.wav"></audio></div></div>`).join('')})</script>"""

if __name__ == "__main__":
    main()
