#!/usr/bin/env python3
"""Plan the recipe re-render of the whole cast (every speaker in jobs_cast_all.jsonl, narrator pieces included).

  python3 tools/render_corpus/plan_cast_r3.py [--out data/render/jobs_cast_r3.jsonl]

Same rules as plan_recipe.py (speech pieces only, cues moved by plan_cast_fix skipped, refs and annotations kept). Vladaym is left out (cast-r2 done).
Narrator pieces must use the BG3 narrator reference; the planner refuses a row whose ref is under prompts/narrator/. Speakers the user
reported as bad get priority 0 so their cues render first (a cue's pieces share its best priority). Writes the jobs file and the cue list for the stitch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from plan_recipe import ROOT, corrected_cues, load_recipe

FIRST = {"Vox Master Vigdis", "High Factotum Janris Danrok", "Octaviana", "Hieronymus Doloroso"}
LEFT_OUT = {"Vladaym Tocara the Liege"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="resat-r2")
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_cast_r3.jsonl"))
    ap.add_argument("--cues-out", default=str(ROOT / "data/render/jobs_cast_r3_cues.jsonl"))
    a = ap.parse_args()
    recipe = load_recipe(a.recipe, ROOT / "data/studio/lab/recipes.json")
    skip = corrected_cues()
    src = [json.loads(ln) for ln in (ROOT / "data/render/jobs_cast_all.jsonl").read_text(encoding="utf-8").splitlines()]
    left_out_cues = {j["parent"] for j in src if j["speaker"] in LEFT_OUT}
    first_cues = {j["parent"] for j in src if j["speaker"] in FIRST}
    rows = []
    for j in src:
        if j.get("seg_kind", "speech") != "speech" or j["parent"] in skip or j["parent"] in left_out_cues:
            continue
        wav = j["ref"]["wav"]
        if "prompts/narrator/" in wav or not (ROOT / wav).is_file():
            raise SystemExit(f"bad reference {wav} on {j['guid']}")
        pr = 0 if j["parent"] in first_cues else j["priority"]
        rows.append({**j, "priority": pr, "recipe": recipe, "respell": False, "routed_from": "recipe:cast-r3"})
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    cues = {r["parent"] for r in rows}
    Path(a.cues_out).write_text("".join(ln + "\n" for ln in (ROOT / "data/render/jobs_cast_all.jsonl").read_text(encoding="utf-8").splitlines()
                                        if json.loads(ln)["parent"] in cues), encoding="utf-8")
    print(f"{len(rows)} pieces in {len(cues)} cues, {sum(len(r['text']) for r in rows) / 900:.0f} audio-min approx -> {a.out}")


if __name__ == "__main__":
    main()
