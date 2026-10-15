#!/usr/bin/env python3
"""Plan the render of the registered automatic BG3 voices (Voice Studio, Assignments page).

  python3 tools/render_corpus/plan_auto_cast.py --out data/render/jobs_auto_cast.jsonl [--recipe resat-r2] [--only KEY ...]
                                                [--skip-done data/render/<run>/manifest.jsonl] [--force]

Takes the items of data/studio/auto_cast.json that the register step put into the prompt bank (prompts.json entries marked `auto_cast`).
A character's lines are the jobs in data/render/jobs.jsonl (read only) whose speaker is the character, plus unnamed cues the Voice Studio
routed to that character by name. A group's lines are the cues whose guid routes to the group in pools.json (the entry is normalised the
way auto_cast.group_targets does). Each job is the original plus: speaker = the item key, ref = the registered clip, the named recipe, and
voice_source = "auto_cast_bg3". Step counts are not set here: queue_server.load_jobs raises processed speakers to 20 steps (processed.py).
Run it as its own queue run so the takes land in their own folder; the guids are the originals, so do not feed it to a run that already has them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools/studio/server"))

from jobs import bucket_of  # noqa: E402
from plan_recipe import load_recipe  # noqa: E402
from plan_mixed import ENGINE  # noqa: E402
from studio_server.auto_cast import GROUP_PREFIX, _norm  # noqa: E402

VOICE_SOURCE = "auto_cast_bg3"
PRIORITY = 1                          # the prompt-bank tier in plan_q21.PRIORITY
CHARS_PER_SECOND = 15                 # the same estimate casting.py uses for audio length


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def registered(root: Path, only: set[str] | None = None) -> dict[str, dict]:
    """item key -> {ref, item} for every assigned auto-cast item whose registered prompt entry is ours."""
    items = (_read(root / "data/studio/auto_cast.json", {}) or {}).get("items", {})
    prompts = _read(root / "data/voices/prompts/prompts.json", {})
    out = {}
    for key, it in items.items():
        e = (prompts.get(key) or [{}])[0]
        if it.get("status") != "assigned" or not e.get("auto_cast") or (only is not None and key not in only):
            continue
        if not (root / "data/voices" / e["wav"]).is_file():
            continue                                                            # registered, but the clip is gone: do not plan a broken ref
        out[key] = {"item": it, "ref": {"wav": f"data/voices/{e['wav']}", "text": e["text"], "emotion": None}}
    return out


def line_owners(root: Path, keys: set[str]) -> dict[str, str]:
    """cue guid -> item key, for the groups (by route entry) and for characters routed to by name."""
    routes = (_read(root / "data/studio/pools.json", {}) or {}).get("routes") or {}
    out = {}
    for guid, r in routes.items():
        if r.get("to") == "slot" and r.get("entry") and GROUP_PREFIX + _norm(r["entry"]) in keys:
            out[guid] = GROUP_PREFIX + _norm(r["entry"])
        elif r.get("to") == "speaker" and r.get("speaker") in keys:
            out[guid] = r["speaker"]
    return out


def build(root: Path, jobs_path: Path, recipe: dict, only: set[str] | None = None, done: set[str] | None = None):
    """(rows, per-key line counts, skipped_done). A character's own lines come from the job's speaker, a group's from its routes."""
    reg = registered(root, only)
    owners = line_owners(root, set(reg))
    rows, seen, skipped_done = [], set(), Counter()
    for ln in jobs_path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        j = json.loads(ln)
        key = owners.get(j["guid"]) if j.get("speaker_kind") == "default_speaker" else (j["speaker"] if j["speaker"] in reg else None)
        if key is None or j["guid"] in seen or not j.get("text"):
            continue
        seen.add(j["guid"])
        if done and j["guid"] in done:
            skipped_done[key] += 1
            continue
        rows.append({**j, "speaker": key, "parent": j["guid"], "seg_index": 0, "seg_kind": "speech", "engine": ENGINE,
                     "bucket": bucket_of(j["guid"]), "priority": PRIORITY, "voice_source": VOICE_SOURCE, "ref": reg[key]["ref"],
                     "recipe": recipe, "respell": False, "routed_from": "auto_cast:" + recipe["name"]})
    return rows, reg, skipped_done


def done_guids(manifest: Path) -> set[str]:
    return {r["guid"] for r in (json.loads(ln) for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.strip()) if r.get("status") == "ok"}


def summary(rows: list[dict], reg: dict, skipped_done: Counter) -> list[str]:
    chars = sum(len(r["text"]) for r in rows)
    per = Counter(r["speaker"] for r in rows)
    steps = Counter(20 if reg[k]["item"].get("processed") else 15 for k in per)
    out = [f"{len(per)} speakers, {len(rows)} lines, {chars:,} chars, about {chars / CHARS_PER_SECOND / 60:.0f} audio minutes",
           f"registered auto-cast items: {len(reg)}; without any line: {len(set(reg) - set(per))}",
           f"speakers by steps (the queue applies 20 to processed ones): {dict(steps)}"]
    if skipped_done:
        out.append(f"skipped as already rendered: {sum(skipped_done.values())} lines")
    return out


def write_out(path: Path, rows: list[dict], force: bool) -> None:
    if path.exists() and not force:
        raise SystemExit(f"{path} exists; pass --force to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")                                    # a watched folder must never see a half-written file
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None, root: Path = ROOT) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--recipe", default="resat-r2")
    ap.add_argument("--only", nargs="+", help="only these item keys (a character name or group:<conversation>|<id>)")
    ap.add_argument("--jobs", default=str(root / "data/render/jobs.jsonl"))
    ap.add_argument("--recipes", default=str(root / "data/studio/lab/recipes.json"))
    ap.add_argument("--skip-done", help="a manifest.jsonl of an earlier run: lines it rendered ok are left out")
    ap.add_argument("--force", action="store_true", help="replace an existing --out")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists() and not a.force:
        raise SystemExit(f"{out} exists; pass --force to replace it")
    done = done_guids(Path(a.skip_done)) if a.skip_done else None
    rows, reg, skipped = build(root, Path(a.jobs), load_recipe(a.recipe, Path(a.recipes)), set(a.only) if a.only else None, done)
    if not rows:
        raise SystemExit("nothing to plan (are the voices registered? is --only a real key?)")
    write_out(out, rows, a.force)
    print("\n".join(summary(rows, reg, skipped)))
    print("wrote", out)


if __name__ == "__main__":
    main()
