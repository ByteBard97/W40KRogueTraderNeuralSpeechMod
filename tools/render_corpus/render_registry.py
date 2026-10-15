#!/usr/bin/env python3
"""Registry of every render run: data/render/registry/registry.json + index.html (static; serve the folder).

  python3 tools/render_corpus/render_registry.py [--export export_all_r3]

Per run (any data/render/<run>/ with a manifest): clip count, audio hours, speakers, recipe / cfg / steps actually used, QC flag
counts, workers, dates, and how many clips of the current export still come from it (matched by hard-link inode, so stitched and
overlaid copies count too). Read-only on everything except the registry folder. Hand notes go in data/render/registry/notes.json
({run: {"note": "...", "status": "..."}}) and are merged in on every build.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "data/render"
OUT = R / "registry"
LEGACY = "legacy: CFG 2.5, 10 steps (render.py default before 2026-10-13)"
R2 = "r2 recipe: CFG 3.0, 15 steps, sentence split, QC retries"


def read_rows(path):
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            yield json.loads(ln)
        except ValueError:
            pass


def day(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def run_info(run_dir):
    rows = list(read_rows(run_dir / "manifest.jsonl"))
    sp, wk, rc, flags = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    cfgs, secs, ok = collections.Counter(), 0.0, 0
    for r in rows:
        if r.get("status") == "ok":
            ok += 1
            secs += r.get("seconds") or 0
        sp[r.get("speaker", "?")] += 1
        wk[r.get("worker", "?")] += 1
        if r.get("recipe"):
            rc[r["recipe"]] += 1
            for c in r.get("cfg_used") or []:
                cfgs[c] += 1
        for fl in r.get("flags") or []:
            flags[fl] += 1
    wavs = run_dir / "wav"
    times = [p.stat().st_mtime for p in wavs.iterdir()] if wavs.is_dir() else []
    mt = (run_dir / "manifest.jsonl").stat().st_mtime
    return {"run": run_dir.name, "rows": len(rows), "ok": ok, "audio_h": round(secs / 3600, 2),
            "pipeline": R2 if rc else LEGACY, "recipes": dict(rc), "cfg_used": {str(k): v for k, v in sorted(cfgs.items())},
            "speakers": sp.most_common(12), "n_speakers": len(sp), "workers": dict(wk), "flags": dict(flags),
            "first": day(min(times)) if times else day(mt), "last": day(max(times) if times else mt), "manifest_mtime": day(mt)}


def inode_owner(run_dirs, extra_dirs):
    """(dev, ino) -> run name, for every wav under a run's wav/ (and *-whole / *-stitched dirs, credited to the run in their name)."""
    owner = {}
    for d in run_dirs + extra_dirs:
        w = d / "wav"
        if w.is_dir():
            for p in w.iterdir():
                st = p.stat()
                owner.setdefault((st.st_dev, st.st_ino), d.name)
    return owner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default="export_all_r3")
    a = ap.parse_args()
    run_dirs = sorted(d for d in R.iterdir() if (d / "manifest.jsonl").is_file() and not d.name.endswith(("-whole", "-stitched")))
    extra = sorted(d for d in R.iterdir() if d.is_dir() and d.name.endswith(("-whole", "-stitched")) and (d / "wav").is_dir())
    runs = [run_info(d) for d in run_dirs]
    owner = inode_owner(run_dirs, extra)
    in_export, unknown = collections.Counter(), 0
    exp = R / a.export / "wav"
    by_speaker = collections.defaultdict(collections.Counter)
    index = json.loads((R / a.export / "index.json").read_text(encoding="utf-8"))
    for guid, meta in index.items():
        p = R / a.export / meta["wav"]
        if not p.is_file():
            continue
        st = p.stat()
        who = owner.get((st.st_dev, st.st_ino))
        if who is None:
            unknown += 1
            who = "(not linked to a run: stitched/mixed copy or older export)"
        in_export[who] += 1
        by_speaker[meta.get("speaker", "?")][who] += 1
    notes = {}
    if (OUT / "notes.json").is_file():
        notes = json.loads((OUT / "notes.json").read_text(encoding="utf-8"))
    for r in runs:
        r["in_export"] = in_export.get(r["run"], 0)
        r["in_export_via_stitch"] = in_export.get(r["run"] + "-stitched", 0) + in_export.get(r["run"] + "-whole", 0)
        r.update(notes.get(r["run"], {}))
    pipe = collections.Counter()
    run_pipe = {r["run"]: r["pipeline"] for r in runs}
    for who, n in in_export.items():
        base = who.removesuffix("-whole").removesuffix("-stitched")
        pipe[run_pipe.get(base, "unknown / stitched from several runs")] += n
    top = {s: dict(c.most_common(4)) for s, c in sorted(by_speaker.items(), key=lambda kv: -sum(kv[1].values()))[:60]}
    OUT.mkdir(exist_ok=True)
    reg = {"generated": day(time.time()), "export": a.export, "export_clips": len(index), "in_export_by_source": dict(in_export.most_common()),
           "in_export_by_pipeline": dict(pipe.most_common()), "runs": sorted(runs, key=lambda r: r["last"]), "speakers_in_export": top}
    (OUT / "registry.json").write_text(json.dumps(reg, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "index.html").write_text(PAGE, encoding="utf-8")
    print(f"{len(runs)} runs, {len(index)} export clips -> {OUT}")
    for k, v in pipe.most_common():
        print(f"  {v:6d}  {k}")


PAGE = r"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Render registry</title>
<style>:root{--bg:#14161a;--fg:#e4e2dc;--mut:#8b8f98;--line:#2b2f37;--acc:#c9a24a;--bad:#d9674f;--ok:#6fbf7a}
body{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:16px 16px 60px;max-width:1300px;margin-inline:auto}
h1{font-size:20px}h2{font-size:15px;margin:26px 0 8px;color:var(--acc)}table{border-collapse:collapse;width:100%}
th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{color:var(--mut);font-weight:500;cursor:pointer}
.n{text-align:right;font-variant-numeric:tabular-nums}.mut{color:var(--mut)}.tag{padding:1px 6px;border-radius:4px;border:1px solid var(--line);font-size:12px}
.r2{color:var(--ok);border-color:var(--ok)}.leg{color:var(--bad);border-color:var(--bad)}.bar{height:14px;background:var(--line);border-radius:3px;overflow:hidden;display:flex}
.bar i{display:block;height:100%}input{background:#1d2026;color:var(--fg);border:1px solid var(--line);padding:5px 8px;border-radius:4px;width:240px}
@media(max-width:700px){.hide{display:none}}</style>
<h1>Render registry</h1><div id=meta class=mut></div>
<h2>What is in the current export, by pipeline</h2><div id=pipe></div>
<h2>Runs</h2><input id=q placeholder="filter runs / speakers"><div style="overflow-x:auto"><table id=runs></table></div>
<h2>Speakers in the export (top 60) and which run their clips come from</h2><div style="overflow-x:auto"><table id=sp></table></div>
<script>
fetch('registry.json').then(r=>r.json()).then(d=>{
const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
meta.textContent=`built ${d.generated} · export ${d.export} · ${d.export_clips.toLocaleString()} clips`;
const tot=d.export_clips;pipe.innerHTML='<table>'+Object.entries(d.in_export_by_pipeline).map(([k,v])=>`<tr><td>${E(k)}</td><td class=n>${v.toLocaleString()}</td><td class=n>${(100*v/tot).toFixed(1)}%</td></tr>`).join('')+'</table>';
const cols=[['run','Run'],['last','Last written'],['pipeline','Pipeline'],['rows','Rows'],['ok','OK'],['audio_h','Audio h'],['in_export','In export'],['in_export_via_stitch','via stitch/whole'],['n_speakers','Speakers'],['flags','Flags'],['note','Note']];
let sort='last',dir=-1;
function draw(){const f=q.value.toLowerCase();let rs=d.runs.filter(r=>!f||JSON.stringify(r).toLowerCase().includes(f));
rs.sort((a,b)=>(a[sort]>b[sort]?1:-1)*dir);
runs.innerHTML='<tr>'+cols.map(c=>`<th data-k=${c[0]}>${c[1]}</th>`).join('')+'</tr>'+rs.map(r=>'<tr>'+cols.map(([k])=>{let v=r[k];
if(k=='pipeline')return `<td><span class="tag ${v.startsWith('r2')?'r2':'leg'}">${v.startsWith('r2')?'r2':'legacy'}</span> <span class=mut>${E(Object.keys(r.recipes).join(', '))} ${Object.entries(r.cfg_used).map(([a,b])=>'cfg'+a+'×'+b).join(' ')}</span></td>`;
if(k=='flags')return `<td class="mut hide">${E(Object.entries(v).map(([a,b])=>a+':'+b).join(' '))}</td>`;
if(k=='run')return `<td title="${E(r.speakers.map(s=>s[0]+' '+s[1]).join('\n'))}">${E(v)}</td>`;
return `<td class="${typeof v=='number'?'n':''}">${v==null?'':E(typeof v=='number'?v.toLocaleString():v)}</td>`}).join('')+'</tr>').join('');
runs.querySelectorAll('th').forEach(t=>t.onclick=()=>{sort=t.dataset.k;dir=-dir;draw()})}
q.oninput=draw;draw();
const pal=['#6fbf7a','#c9a24a','#5b9bd5','#d9674f','#a37fd1','#888'];
sp.innerHTML='<tr><th>Speaker</th><th class=n>Clips</th><th>Sources</th></tr>'+Object.entries(d.speakers_in_export).map(([s,c])=>{const t=Object.values(c).reduce((a,b)=>a+b,0);
return `<tr><td>${E(s)}</td><td class=n>${t}</td><td>${Object.entries(c).map(([k,v],i)=>`<span class=tag style="border-color:${pal[i%6]}">${E(k)} ${v}</span>`).join(' ')}</td></tr>`}).join('')});
</script>"""

if __name__ == "__main__":
    main()
