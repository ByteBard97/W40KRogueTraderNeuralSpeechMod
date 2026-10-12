#!/usr/bin/env python3
"""Whole-line vs split-and-stitched listening test for long lines (HANDOFF 2026-10-07).

Picks lines from data/npc_profile/seg_long.jsonl (6 strong splits, 4 doubtful ones), renders each once whole and once
per segment with VoxCPM2 (same reference clip for every piece), stitches the segments, and writes a blind A/B page.

  /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/render_corpus/ab_split.py [--strong 6] [--doubtful 4]
  cd data/render/ab_split && python3 -m http.server 8909
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
from render import load_engine  # noqa: E402
from stitch import stitch  # noqa: E402

OUT = ROOT / "data/render/ab_split"


def pick(strong: int, doubtful: int, seed: int) -> list[dict]:
    segs = {r["guid"]: r for r in map(json.loads, (ROOT / "data/npc_profile/seg_long.jsonl").open(encoding="utf-8"))}
    tri = json.loads((ROOT / "data/npc_profile/seg_long_triage.json").read_text(encoding="utf-8"))
    rng = random.Random(seed)
    guids = rng.sample(tri["strong"], strong) + rng.sample(tri["doubtful"], doubtful)
    jobs = {j["guid"]: j for j in map(json.loads, (ROOT / "data/render/jobs.jsonl").open(encoding="utf-8")) if j["guid"] in guids}
    return [{"seg": segs[g], "job": jobs[g], "group": "strong" if g in tri["strong"] else "doubtful"} for g in guids]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strong", type=int, default=6)
    ap.add_argument("--doubtful", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    items = pick(args.strong, args.doubtful, args.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    synth = load_engine("voxcpm2")
    rng = random.Random(args.seed)
    pairs = []
    for it in items:
        job, seg = it["job"], it["seg"]
        ref = {"wav": str(ROOT / job["ref"]["wav"]), "text": job["ref"]["text"]}
        wav, sr = synth(job["text"], ref, job["annotation"])
        pieces = []
        for s in seg["segments"]:
            a = {"emotion": s["emotion"], "intensity": s.get("intensity_value", 0.5), "pace": s["pace"],
                 "nonverbal": [], "instruct": s["instruct"]}
            w, sr2 = synth(s["text"], ref, a)
            pieces.append(np.asarray(w, dtype=np.float32))
        split = stitch(pieces, sr)
        g = job["guid"]
        whole_first = rng.random() < 0.5
        files = {"whole": f"{g}_whole.wav", "split": f"{g}_split.wav"}
        sf.write(OUT / files["whole"], np.asarray(wav, dtype=np.float32).reshape(-1), sr)
        sf.write(OUT / files["split"], split, sr)
        a_kind, b_kind = ("whole", "split") if whole_first else ("split", "whole")
        pairs.append({"guid": g, "group": it["group"], "speaker": job["speaker"], "text": job["text"],
                      "a": files[a_kind], "b": files[b_kind], "a_is": a_kind, "b_is": b_kind,
                      "n_segments": len(seg["segments"]),
                      "boundary_conf": [round(s["conf"]["end_sentence"], 2) for s in seg["segments"][:-1]]})
        print(f"{len(pairs)}/{len(items)} {g} {it['group']} segs={len(pieces)}", flush=True)
    (OUT / "pairs.json").write_text(json.dumps(pairs, indent=1), encoding="utf-8")
    (OUT / "index.html").write_text(PAGE, encoding="utf-8")
    print(f"page: {OUT}/index.html  (serve with http.server)")


PAGE = """<!doctype html><meta charset=utf-8><title>Whole vs split</title>
<style>body{font:15px system-ui;max-width:760px;margin:20px auto;padding:0 16px;background:#161616;color:#ddd}
.p{border:1px solid #333;border-radius:8px;padding:12px;margin:14px 0}.t{color:#999;font-size:13px;max-height:4.5em;overflow:auto}
audio{width:100%;margin:4px 0}label{margin-right:14px}button{padding:6px 12px}.k{color:#e9a}</style>
<h2>Whole vs split</h2><p>For each pair: which sounds better as one performance? Tick the box if you hear a seam, a jump in voice or loudness, or a weird pause.</p>
<div id=l></div><button onclick=done()>Show results</button> <button onclick=dl()>Download JSON</button><pre id=r></pre>
<script>
let P=[],R={};fetch('pairs.json').then(r=>r.json()).then(p=>{P=p;draw()});
function draw(){l.innerHTML=P.map((p,i)=>`<div class=p><b>${i+1}</b> <span class=t>${p.text}</span>
<div>A <audio controls src="${p.a}"></audio></div><div>B <audio controls src="${p.b}"></audio></div>
<label><input type=radio name=c${i} value=a onchange="R[${i}]=R[${i}]||{};R[${i}].pick='a'">A better</label>
<label><input type=radio name=c${i} value=b onchange="R[${i}]=R[${i}]||{};R[${i}].pick='b'">B better</label>
<label><input type=radio name=c${i} value=same onchange="R[${i}]=R[${i}]||{};R[${i}].pick='same'">same</label>
<label><input type=checkbox onchange="R[${i}]=R[${i}]||{};R[${i}].seam=this.checked">I hear a seam</label></div>`).join('')}
function out(){return P.map((p,i)=>({n:i+1,guid:p.guid,group:p.group,segments:p.n_segments,boundary_conf:p.boundary_conf,
 pick:(R[i]||{}).pick,preferred:(R[i]||{}).pick==='a'?p.a_is:(R[i]||{}).pick==='b'?p.b_is:(R[i]||{}).pick,seam:!!(R[i]||{}).seam}))}
function done(){const o=out();r.textContent=o.map(x=>`${x.n} ${x.group}: preferred ${x.preferred||'-'}${x.seam?' (seam heard)':''}`).join('\\n')+
 '\\n\\nsplit wins: '+o.filter(x=>x.preferred==='split').length+'  whole wins: '+o.filter(x=>x.preferred==='whole').length}
function dl(){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out(),null,1)]));a.download='ab_split_results.json';a.click()}
</script>"""

if __name__ == "__main__":
    main()
