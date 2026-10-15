#!/usr/bin/env python3
"""Plan the render for the 21 conversations whose speaker questions were answered (tools/npc_profile/q21_answers.py).

  python3 tools/render_corpus/plan_q21.py [--out data/render/jobs_q21.jsonl] [--max-chars 1200] [--dry-run]

Reads data/render/jobs.jsonl (read only), data/npc_profile/human_labels.json (`voices` per conversation), segments.json and the
installed export's index. A line is planned only when its target voice differs from the speaker already rendered in the export
(or it was never rendered, or it is an annotated multi-speaker cue). Every cue becomes pieces "<guid>~q<k>" with parent = the cue:
a character plus narration is split like plan_mixed, an annotated cue like plan_annotated, and any piece over --max-chars is cut
at sentence boundaries (split_long.chunks) so no single generation can run the GPU out of memory (a 3,900 character text did).
stitch_mixed.py joins the pieces back into one take per cue. Prints what it did not plan: lines with no voice mapped.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))

from clean_text import clean_for_tts  # noqa: E402
from jobs import bucket_of, decode_binary  # noqa: E402
from plan import ALIASES, _narrator_ref, _ref  # noqa: E402
from plan_mixed import ENGINE, segment_jobs  # noqa: E402
from segment_annotations import load as load_segments, validate  # noqa: E402
from split_long import chunks  # noqa: E402

PRIORITY = {"emotion_bank": 0, "prompt_bank": 1, "narrator": 2, "fallback": 3}
# annotated cues whose segment speakers are display names, not voices (segments.json entries without a "voice")
SEGMENT_VOICES = {"Scout 1": "pool_male_human", "Lookout": "pool_male_human_young"}
EXPORT = "export_all_night"


def piece(job: dict, k: int, speaker: str, text: str, ref: dict, source: str, annotation) -> dict:
    return {**{f: job[f] for f in ("speaker_kind", "src_text") if f in job},
            "guid": f"{job['guid']}~q{k}", "parent": job["guid"], "seg_index": k, "seg_kind": "speech", "speaker": speaker,
            "text": text, "engine": ENGINE, "bucket": bucket_of(job["guid"]), "priority": PRIORITY[source], "voice_source": source,
            "ref": ref, "annotation": annotation, "routed_from": "q21"}


def cue_pieces(job: dict, target: str, ref_fn, narrator_ref: dict, entry: dict | None) -> list[tuple]:
    """[(speaker, text, ref, source, annotation)] in cue order."""
    ann = job.get("annotation")
    emo = (ann or {}).get("emotion")
    out = []
    if entry is not None:
        from plan_annotated import annotated_jobs
        segs = []
        for x in entry["segments"]:    # speaker becomes the voice key, so loudness targets and the manifest name a real voice
            voice = x.get("voice") or SEGMENT_VOICES.get(x["speaker"], x["speaker"])
            segs.append({**x, "voice": voice, "speaker": x["speaker"] if x["kind"] == "narration" or x["speaker"] == "narrator" else voice})
        for s in annotated_jobs(job, {"segments": segs}, narrator_ref, ref_fn):
            out.append((s["speaker"], s["text"], s["ref"], s["voice_source"], s["annotation"]))
        return out
    if target == "narrator":
        return [("narrator", job["text"], dict(narrator_ref, emotion=None), "narrator", None)]
    ref, source = ref_fn(target, emo)
    tmp = {**job, "speaker": target, "ref": ref, "voice_source": source, "priority": PRIORITY[source]}
    segs = segment_jobs(tmp, narrator_ref)
    if not segs:
        return [(target, job["text"], ref, source, ann)]
    for s in segs:
        out.append((s["speaker"], s["text"], s["ref"], s["voice_source"], ann if s["speaker"] == target else None))
    return out


def cap(pieces: list[tuple], max_chars: int) -> list[tuple]:
    out = []
    for sp, text, ref, source, ann in pieces:
        parts = chunks(text, max_chars) if len(text) > max_chars else [text]
        out += [(sp, t, ref, source, ann) for t in parts]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_q21.jsonl"))
    ap.add_argument("--max-chars", type=int, default=1200)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    labels = json.loads((ROOT / "data/npc_profile/human_labels.json").read_text(encoding="utf-8"))["conversations"]
    jobs = {}
    for ln in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        j = json.loads(ln)
        jobs.setdefault(j["guid"], j)
    exp = json.loads((ROOT / "data" / "render" / EXPORT / "index.json").read_text(encoding="utf-8"))
    segments = load_segments()
    texts = {ln["text_key"]: ln["text"] for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
             for ln in c["lines"] if ln.get("text_key") in segments and ln.get("text")}
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    libs: dict = {}
    ref_fn = lambda v, e: _ref(prompts, libs, ALIASES.get(v, v), e, False)  # noqa: E731
    narrator = _narrator_ref()
    rows, per_conv, problems = [], defaultdict(Counter), []
    for name, entry in labels.items():
        voices = entry.get("voices")
        if not voices:
            continue
        for guid, l in entry["lines"].items():
            job = jobs.get(guid)
            if job is None:
                problems.append(f"{name}: {guid} not in jobs.jsonl")
                continue
            target = "narrator" if l["speaker"] == "NARRATOR" else voices.get(l["speaker"])
            if target is None:
                problems.append(f"{name}: no voice for roster id {l['speaker']!r}")
                continue
            seg = segments.get(guid)
            if seg is not None and (guid not in texts or validate(texts[guid], seg)):
                problems.append(f"{name}: annotation for {guid} no longer matches the text")
                seg = None
            if seg is None and guid in exp and exp[guid].get("speaker") == target:
                per_conv[name]["already_right"] += 1
                continue
            ps = cap(cue_pieces(job, target, ref_fn, narrator, seg), a.max_chars)
            for k, (sp, text, ref, source, ann) in enumerate(ps):
                if source == "fallback":
                    problems.append(f"{name}: {sp} resolved to the fallback voice ({guid})")
                rows.append({**piece(job, k, sp, text, ref, source, ann), "seg_count": len(ps)})
            per_conv[name]["cues"] += 1
            per_conv[name]["pieces"] += len(ps)
    for name, c in per_conv.items():
        print(f"{name:42s} cues {c['cues']:3d} pieces {c['pieces']:3d} already right {c['already_right']:3d}")
    chars = [len(r["text"]) for r in rows]
    print(f"\n{len({r['parent'] for r in rows})} cues -> {len(rows)} pieces, {sum(chars)} chars, longest piece {max(chars, default=0)}")
    print("by voice:", dict(Counter(r["speaker"] for r in rows)))
    for p in sorted(set(problems)):
        print("PROBLEM", p)
    if not a.dry_run:
        Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print("wrote", a.out)


if __name__ == "__main__":
    main()
