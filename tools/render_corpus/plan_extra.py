#!/usr/bin/env python3
"""Plan the narrator-voice render of the strings that have an AIVO bank clip but are not dialogue cues.

These are codex and book text, item and ability descriptions, quest log lines, names and UI strings
(11,767 of them on 2026-10-07). plan.py only covers conversation cues, so none of these are in jobs.jsonl.
A string counts as "in the bank" when the AIVO bank has an event ev_<guid> that tools/bnk_patch can swap.

  python3 tools/render_corpus/plan_extra.py --bank ~/rt-mods/full-banks/w40krt_avio_charvogen.bnk [--out data/render/jobs_extra.jsonl]

Every job uses the narrator reference from jobs_narr_bg3.jsonl, so render.py can run it unchanged. `category`
lets you filter before rendering (render.py ignores it): quoted | long | short_name | sentence.
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
sys.path.insert(0, str(ROOT / "tools/bnk_patch"))

from build_test_set import narration_only  # noqa: E402
from clean_text import clean_for_tts, is_terminal_log  # noqa: E402
from jobs import bucket_of, choose_engine, decode_binary  # noqa: E402

LONG_CHARS = 1200      # past this VoxCPM2 drifts on one take; these need splitting before rendering
SHORT_NAME_WORDS = 4
JUNK = re.compile(r"^(placeholder|test|todo|tbd|xxx)\b", re.I)
LEFTOVER_TAG = re.compile(r"\{[^{}]*\}")
SPACED_BINARY = re.compile(r"(?<![01])(?:[01]{8} ){1,}[01]{8}(?![01])")
ENTITIES = {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&nbsp;": " "}


def clean(text: str) -> str:
    t = narration_only(text)
    for k, v in ENTITIES.items():
        t = t.replace(k, v)
    t = LEFTOVER_TAG.sub("", t)   # {count}, {target}: runtime fill-ins with nothing to speak
    t = SPACED_BINARY.sub(lambda m: m.group(0).replace(" ", ""), t)   # "01000101 01111000" -> one run decode_binary can read
    t = re.sub(r"\*{2,}", " ", t).replace('"', " ")   # divider asterisks; quote marks are not spoken (as in speech_only)
    return clean_for_tts(re.sub(r"\s+", " ", decode_binary(t)))


def classify(spoken: str, src: str) -> str:
    if len(spoken) >= LONG_CHARS:
        return "long"
    if '"' in src or "“" in src:
        return "quoted"
    return "short_name" if len(spoken.split()) <= SHORT_NAME_WORDS else "sentence"


def skip_reason(spoken: str) -> str | None:
    if not re.search(r"[A-Za-z]", spoken):
        return "no_latin_text"      # blank, numbers only, or non-English placeholder strings
    if JUNK.match(spoken):
        return "junk"
    if len(re.findall(r"[A-Za-z]", spoken)) < 2:
        return "one_letter"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", required=True)
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_extra.jsonl"))
    args = ap.parse_args()
    from bank import Bank
    bank = Bank(str(Path(args.bank).expanduser()))

    strings = json.loads((ROOT / "data/strings.enGB.json").read_text(encoding="utf-8"))
    taken = {json.loads(ln)["guid"] for ln in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines()}
    ref = json.loads(next(iter((ROOT / "data/render/jobs_narr_bg3.jsonl").open(encoding="utf-8"))))["ref"]

    jobs, skipped, seen = [], Counter(), set()
    for s in strings:
        g = s["key"]
        if g in taken or g in seen or bank.media_for_guid(g) is None:
            continue
        seen.add(g)
        spoken = clean(s["text"])
        why = "terminal_log" if is_terminal_log(narration_only(s["text"])) else skip_reason(spoken)
        if why:
            skipped[why] += 1
            continue
        jobs.append({"guid": g, "speaker": "narrator", "speaker_kind": "string", "text": spoken, "src_text": s["text"],
                     "annotation": None, "engine": choose_engine(spoken), "bucket": bucket_of(g), "priority": 2,
                     "voice_source": "narrator", "ref": ref, "category": classify(spoken, s["text"])})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
    chars = sum(len(j["text"]) for j in jobs)
    print(f"{len(jobs)} jobs -> {out} ({chars/1e6:.2f}M chars, ~{chars/15/3600:.1f} h audio), skipped {dict(skipped)}")
    print("by category:", dict(Counter(j["category"] for j in jobs)))
    print("by engine:", dict(Counter(j["engine"] for j in jobs)))


if __name__ == "__main__":
    main()
