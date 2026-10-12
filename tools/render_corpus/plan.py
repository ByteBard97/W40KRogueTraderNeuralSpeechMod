#!/usr/bin/env python3
"""Build data/render/jobs.jsonl: one render job per unique unvoiced dialogue cue.

Each job fixes the text to speak, the voice (reference clip), the annotation and the engine, so any
machine can render any subset with render.py. Voices come from data/voices/prompts/prompts.json (top
clip per speaker), upgraded to an emotion-matched clip where curation.json has ear-verified clips for
that speaker. Speakers without a bank (default_speaker, one-off NPCs) fall back to the narrator voice
and are flagged voice_source="fallback" so a later pass can re-plan just those.

Usage: python3 tools/render_corpus/plan.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))

from build_test_set import narration_only, speech_only  # noqa: E402
from clean_text import clean_for_tts, is_terminal_log  # noqa: E402
from jobs import bucket_of, choose_engine, decode_binary  # noqa: E402
from pool_routes import load_routes, resolve  # noqa: E402

OUT = ROOT / "data/render/jobs.jsonl"
PROMPTS = ROOT / "data/voices/prompts/prompts.json"
MIN_REF_SECONDS = 5.5
# conversation speaker name -> prompt bank key, where they differ
ALIASES = {"Trazyn": "Trazyn the Infinite"}
# Speaker kinds with no identity of their own. An unquoted line from one of these is narration
# (epilogues, dossiers, placeholders), not someone speaking, so it gets the narrator voice.
UNNAMED_KINDS = {"default_speaker", "unit"}


def is_unquoted_narration(kind: str | None, text: str) -> bool:
    return kind in UNNAMED_KINDS and '"' not in text


def _bank_clip(bank: list[dict]) -> dict | None:
    usable = [p for p in bank if p.get("duration", 0) >= MIN_REF_SECONDS] or bank
    return usable[0] if usable else None


def _narrator_ref() -> dict:
    """Real BG3 narrator clip (rank 1 of narrator_bg3; the old prompts/narrator clips are Gale)."""
    r = json.loads((ROOT / "data/voices/prompts/narrator_bg3/refs.json").read_text())[0]
    return {"wav": r["wav"], "text": r["text"]}


def _ref(prompts: dict, libs: dict, speaker: str | None, emotion: str | None, is_narrator: bool) -> tuple[dict, str]:
    """(reference {wav,text,emotion}, voice_source) for a speaker."""
    key = ALIASES.get(speaker, speaker)
    if key in prompts and key != "narrator":
        if key not in libs:
            try:
                from select_reference_clip import ReferenceLibrary
                libs[key] = ReferenceLibrary(key)
            except SystemExit:  # no ear-verified emotion bank for this speaker
                libs[key] = None
        lib = libs[key]
        if lib is not None and emotion:
            r = lib.find(emotion)
            return {"wav": str(Path(r["wav"]).relative_to(ROOT)), "text": r["text"],
                    "emotion": r.get("matched_emotion") or r["emotion"]}, "emotion_bank"
        p = _bank_clip(prompts[key])
        return {"wav": f"data/voices/{p['wav']}", "text": p["text"], "emotion": None}, "prompt_bank"
    src = "narrator" if is_narrator else "fallback"
    return dict(_narrator_ref(), emotion=None), src


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
    ann = json.loads((ROOT / "data/annotations/annotations.enGB.json").read_text(encoding="utf-8"))
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))

    libs: dict = {}
    routes = load_routes()
    jobs, seen, skipped = [], set(), Counter()
    for conv in convs:
        for line in conv["lines"]:
            if line.get("kind") != "cue" or not line.get("text") or line.get("voiced"):
                continue
            guid = line["text_key"]
            if guid in seen:
                continue
            seen.add(guid)
            sp = line["speaker"]
            kind, name = sp.get("kind"), sp.get("name")
            raw = decode_binary(speech_only(line["text"]))
            spoken = clean_for_tts(raw)
            as_narration = False
            if is_unquoted_narration(kind, line["text"]) or not re.search(r"[A-Za-z]", spoken):
                raw = decode_binary(narration_only(line["text"]))
                spoken, as_narration = clean_for_tts(raw), True
                if not re.search(r"[A-Za-z]", spoken):
                    skipped["no_text"] += 1
                    continue
            if re.search(r"[\u0400-\u04ff]|^\[Draft\]", line["text"]):   # developer test strings (Cyrillic, "[Draft] Test ...")
                skipped["test_string"] += 1
                continue
            a = ann.get(guid) or {}
            is_narrator = as_narration or kind == "narrator"
            if is_narrator and is_terminal_log(raw):
                skipped["terminal_log"] += 1
                continue
            speaker = "narrator" if is_narrator else name
            speaker, is_narrator, routed_from = resolve(routes, guid, kind, speaker, is_narrator)
            ref, source = _ref(prompts, libs, speaker, a.get("emotion"), is_narrator)
            priority = {"emotion_bank": 0, "prompt_bank": 1, "narrator": 2, "fallback": 3}[source]
            jobs.append({
                "guid": guid, "speaker": speaker or kind, "speaker_kind": kind,
                "text": spoken, "src_text": line["text"], "annotation": a or None,
                "engine": choose_engine(spoken), "bucket": bucket_of(guid), "priority": priority,
                "voice_source": source, "ref": ref,
                **({"routed_from": routed_from} if routed_from else {}),
            })
            if args.limit and len(jobs) >= args.limit:
                break
        if args.limit and len(jobs) >= args.limit:
            break

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    chars = sum(len(j["text"]) for j in jobs)
    print(f"{len(jobs)} jobs -> {OUT}  ({chars/1e6:.2f}M chars, skipped {dict(skipped)})")
    print("by voice source:", dict(Counter(j["voice_source"] for j in jobs)))
    print("by engine:", dict(Counter(j["engine"] for j in jobs)))


if __name__ == "__main__":
    main()
