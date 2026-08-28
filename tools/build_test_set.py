#!/usr/bin/env python3
"""Build the fixed TTS bake-off test set: unvoiced lines per companion + narration passages.

Selection per companion (from conversations.enGB.json):
  - unvoiced cues only (that's the mod's actual job)
  - spread across tone: exclamatory, questioning, long/expository, short/reactive
  - plain text (markup stripped), quotes removed, narration {n}..{/n} segments dropped -
    the bake-off synthesizes the *speech* part only
Narrator set: pure narration cues (is_narrator_text / narrator speaker), varied length.

Output: data/tts_test_set.json - [{id, speaker, kind, text, source_key}]
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPANIONS = ["Abelard", "Argenta", "Cassia", "Heinrix", "Idira", "Jae", "Pasqal",
              "Yrliet", "Marazhai", "Ulfar", "Kibellah", "Solomorne", "Eogunn"]
N_PER_SPEAKER = 10
N_NARRATOR = 12

NARR_SEG = re.compile(r"\{n\}.*?\{/n\}", re.S)
TAG = re.compile(r"\{[^}]*\}|<[^>]*>")


def speech_only(text: str) -> str:
    """Drop narration segments, keep quoted/spoken text, strip markup and quotes."""
    t = NARR_SEG.sub(" ", text)
    t = TAG.sub("", t)
    t = t.replace("—", ", ").replace('"', " ")
    return re.sub(r"\s+", " ", t).strip()


def narration_only(text: str) -> str:
    t = TAG.sub("", text)
    return re.sub(r"\s+", " ", t).strip()


def pick_varied(lines: list[dict], n: int) -> list[dict]:
    """Greedy pick across tone buckets for coverage."""
    buckets = {
        "exclaim": [l for l in lines if "!" in l["text"]],
        "question": [l for l in lines if "?" in l["text"]],
        "short": sorted(lines, key=lambda l: len(l["text"]))[: max(4, n)],
        "long": sorted(lines, key=lambda l: -len(l["text"]))[: max(4, n)],
        "mid": [l for l in lines if 80 <= len(l["text"]) <= 200],
    }
    chosen, seen = [], set()
    order = ["exclaim", "question", "long", "short", "mid"]
    i = 0
    while len(chosen) < n and any(buckets.values()):
        b = buckets[order[i % len(order)]]
        i += 1
        while b:
            cand = b.pop(0)
            if cand["source_key"] not in seen:
                seen.add(cand["source_key"])
                chosen.append(cand)
                break
    return chosen


def main() -> None:
    convs = json.load(open(ROOT / "data/conversations.enGB.json", encoding="utf-8"))
    per_speaker: dict[str, list] = {c: [] for c in COMPANIONS}
    narrator: list[dict] = []

    for conv in convs:
        for l in conv.get("lines", []):
            if l.get("kind") != "cue" or not l.get("text") or l.get("voiced"):
                continue
            sp = l.get("speaker") or {}
            name = sp.get("name")
            if name in per_speaker:
                t = speech_only(l["text"])
                if len(t) >= 25:
                    per_speaker[name].append({"speaker": name, "kind": "dialogue",
                                              "text": t, "source_key": l["text_key"]})
            elif sp.get("kind") == "narrator":
                t = narration_only(l["text"])
                if len(t) >= 60:
                    narrator.append({"speaker": "narrator", "kind": "narration",
                                     "text": t, "source_key": l["text_key"]})

    test = []
    for c in COMPANIONS:
        for item in pick_varied(per_speaker[c], N_PER_SPEAKER):
            test.append(item)
    for item in pick_varied(narrator, N_NARRATOR):
        test.append(item)
    for i, item in enumerate(test):
        item["id"] = f"t{i:03d}"

    out = ROOT / "data/tts_test_set.json"
    out.write_text(json.dumps(test, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(test)} test lines -> {out}")
    for c in COMPANIONS:
        n = sum(1 for t in test if t["speaker"] == c)
        print(f"  {c}: {n}")
    print(f"  narrator: {sum(1 for t in test if t['speaker'] == 'narrator')}")


if __name__ == "__main__":
    main()
