#!/usr/bin/env python3
"""Plan the lines of characters that have no voice bank, using generated descriptions (data/npc_profile/describe/descriptions.json).

  python3 tools/render_corpus/plan_voiceless.py [--out data/render/jobs_voiceless.jsonl] [--max-chars 1200] [--dry-run]

Takes every job in data/render/jobs.jsonl (read only) that is still on the fallback voice and has no take in the installed export
nor in the q21 plan. The speaker is the cue's named speaker, or for an unnamed cue the speaker the Voice Studio routed it to
(data/studio/pools.json). The voice is the speaker's own registered voice when prompts.json has one (a designed voice), otherwise the
pool slot the description names. Pieces, caps and names follow plan_q21.py ("<guid>~q<k>", parent = the cue); stitch_mixed.py joins them.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))

from plan import ALIASES, _narrator_ref, _ref  # noqa: E402
from plan_q21 import EXPORT, cap, cue_pieces, piece  # noqa: E402
from pool_routes import load_routes  # noqa: E402


NO_CLIP = {"pool_female_machine": "pool_male_machine"}    # the slot has no registered clip yet


def voice_for(speaker: str, desc: dict, prompts: dict) -> str | None:
    speaker = NO_CLIP.get(speaker, speaker)
    if speaker in prompts:
        return speaker
    slot = (desc.get(speaker) or {}).get("pool_slot")
    return f"pool_{slot}" if slot and f"pool_{slot}" in prompts else None


def build(jobs_path: Path, max_chars: int, only: set[str] | None = None) -> tuple[list[dict], Counter, Counter]:
    """Pieces for the voiceless lines. With `only`, every line of just those speakers (even ones already rendered: a newly cast voice
    replaces the old take), each in the speaker's own registered voice; without it, every still-unrendered fallback line."""
    desc = json.loads((ROOT / "data/npc_profile/describe/descriptions.json").read_text(encoding="utf-8"))
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    exp = json.loads((ROOT / "data/render" / EXPORT / "index.json").read_text(encoding="utf-8"))
    q21 = {json.loads(ln)["parent"] for ln in (ROOT / "data/render/jobs_q21.jsonl").read_text(encoding="utf-8").splitlines()}
    routes = load_routes()
    libs: dict = {}
    ref_fn = lambda v, e: _ref(prompts, libs, ALIASES.get(v, v), e, False)  # noqa: E731
    narrator = _narrator_ref()
    rows, stats, missing = [], Counter(), Counter()
    for line in jobs_path.read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        speaker = job["speaker"]
        if job["speaker_kind"] == "default_speaker":
            r = routes.get(job["guid"])
            speaker = r["speaker"] if r and r.get("speaker") else None
        if only is not None:
            if speaker not in only:
                continue
        elif job["voice_source"] != "fallback" or job["guid"] in exp or job["guid"] in q21:
            continue
        voice = (speaker if speaker in prompts else None) if only is not None else (voice_for(speaker, desc, prompts) if speaker else None)
        if voice is None:
            missing[speaker or "(unrouted unnamed)"] += 1
            continue
        ps = cap(cue_pieces(job, voice, ref_fn, narrator, None), max_chars)
        for k, (sp, text, ref, source, ann) in enumerate(ps):
            rows.append({**piece(job, k, sp, text, ref, source, ann), "seg_count": len(ps), "routed_from": "cast" if only is not None else "voiceless"})
        stats["cues"] += 1
    return rows, stats, missing


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_voiceless.jsonl"))
    ap.add_argument("--max-chars", type=int, default=1200)
    ap.add_argument("--speakers", nargs="+", help="only these speakers, all of their lines, in their registered voice (see cast_ready.py)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows, stats, missing = build(Path(a.jobs), a.max_chars, set(a.speakers) if a.speakers else None)
    chars = [len(r["text"]) for r in rows]
    print(f"{stats['cues']} cues -> {len(rows)} pieces, {sum(chars):,} chars (~{sum(chars) / 15 / 3600:.0f} audio-h), longest piece {max(chars, default=0)}")
    print("by voice:", dict(Counter(r["speaker"] for r in rows).most_common()))
    print(f"not planned (no description or route): {sum(missing.values())} lines", dict(missing.most_common(8)))
    if not a.dry_run:
        Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print("wrote", a.out)


if __name__ == "__main__":
    main()
