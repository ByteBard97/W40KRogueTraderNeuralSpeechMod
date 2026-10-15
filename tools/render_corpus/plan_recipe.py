#!/usr/bin/env python3
"""Plan a recipe render: one job per speech piece of a cast speaker, carrying the Render Lab recipe.

  python3 tools/render_corpus/plan_recipe.py --speaker "Vladaym Tocara the Liege" --recipe vladaym-r2 [--out data/render/jobs_cast_r2.jsonl]

Reads data/render/jobs_cast_all.jsonl (the cast render's pieces) and the saved recipe in data/studio/lab/recipes.json. Pieces keep their
guids, ref and annotation; the worker (recipe_render.py) does the splitting, pronunciation, joining and quality control. Run the queue
as a separate run (`queue_server.py --run cast-r2 --jobs <out> --port 8953`) and stitch with `--runs cast-r2 cast` so these takes win.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_recipe(name: str, recipes_path: Path) -> dict:
    saved = json.loads(recipes_path.read_text(encoding="utf-8")) if recipes_path.is_file() else []
    for r in saved:
        if r["name"] == name:
            return r
    raise SystemExit(f"no saved recipe {name!r} in {recipes_path} (save it in the Render Lab first)")


def corrected_cues(root: Path = ROOT) -> set[str]:
    """Cues the ground truth moved to another speaker (plan_cast_fix.py): the cast list still names the old speaker, so skip them."""
    p = root / "data/render/jobs_cast_fix.jsonl"
    return {json.loads(ln)["parent"] for ln in p.read_text(encoding="utf-8").splitlines()} if p.is_file() else set()


def plan(jobs_path: Path, speaker: str, recipe: dict, skip: set[str] | None = None) -> list[dict]:
    rows = []
    for ln in jobs_path.read_text(encoding="utf-8").splitlines():
        j = json.loads(ln)
        if j["speaker"] == speaker and j.get("seg_kind", "speech") == "speech" and j["parent"] not in (skip or set()):
            rows.append({**j, "recipe": recipe, "respell": False, "routed_from": "recipe:" + recipe["name"]})
    return rows


def plan_with_ref(jobs_path: Path, speaker: str, recipe: dict, ref: dict) -> list[dict]:
    """Every job of `speaker` in a jobs file with no cue structure (the codex / item strings), re-pointed at `ref`."""
    rows = []
    for ln in jobs_path.read_text(encoding="utf-8").splitlines():
        j = json.loads(ln)
        if j["speaker"] == speaker:
            rows.append({**j, "ref": ref, "recipe": recipe, "respell": False, "routed_from": "recipe:" + recipe["name"]})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", required=True)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs_cast_all.jsonl"))
    ap.add_argument("--recipes", default=str(ROOT / "data/studio/lab/recipes.json"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_cast_r2.jsonl"))
    ap.add_argument("--cues-out", default=str(ROOT / "data/render/jobs_cast_r2_cues.jsonl"),
                    help="every piece of the affected cues (for the stitch: the other speakers' pieces keep their cast takes)")
    ap.add_argument("--ref", help="re-point every job of the speaker at this wav (needs --ref-text); the jobs file has no cue structure")
    ap.add_argument("--ref-text", help="transcript of --ref")
    a = ap.parse_args()
    if a.ref:
        ref = {"wav": a.ref, "text": a.ref_text, "emotion": None}
        rows = plan_with_ref(Path(a.jobs), a.speaker, load_recipe(a.recipe, Path(a.recipes)), ref)
        bad = [r["guid"] for r in rows if "prompts/narrator/" in r["ref"]["wav"] or not (ROOT / r["ref"]["wav"]).is_file()]
        if not rows or bad or not a.ref_text:
            raise SystemExit(f"refusing: {len(rows)} rows, {len(bad)} with a bad reference, ref text given: {bool(a.ref_text)}")
        Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"{len(rows)} jobs, {sum(len(r['text']) for r in rows)} chars, all with ref {a.ref} -> {a.out}")
        return
    skip = corrected_cues()
    rows = plan(Path(a.jobs), a.speaker, load_recipe(a.recipe, Path(a.recipes)), skip)
    if not rows:
        raise SystemExit(f"no speech pieces for {a.speaker!r}")
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    cues = {r["parent"] for r in rows}
    whole = [ln for ln in Path(a.jobs).read_text(encoding="utf-8").splitlines() if json.loads(ln)["parent"] in cues]
    Path(a.cues_out).write_text("\n".join(whole) + "\n", encoding="utf-8")
    chars = sum(len(r["text"]) for r in rows)
    print(f"{len(rows)} pieces in {len(cues)} cues, {chars} chars -> {a.out} (skipped {len(skip)} corrected cues; stitch list {a.cues_out})")


if __name__ == "__main__":
    main()
