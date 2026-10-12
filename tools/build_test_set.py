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
TAG_OPEN = re.compile(r"\{([a-zA-Z]+)(?:\|([^}]*))?\}")
TAG_CLOSE = re.compile(r"\{/[a-zA-Z]+\}|<[^>]*>")
# The game addresses the player character as "Lord Captain" throughout (confirmed in-corpus,
# e.g. plain dialogue lines like "Lord Captain, wait!") - {name}/{petName} placeholders are
# normally filled with the player's chosen name at runtime; since no name exists here, dropping
# the tag entirely leaves an audible gap/stray punctuation (e.g. "Very well, . I shall..."), so
# substitute the same generic address the game itself falls back to instead.
PLAYER_ADDRESS = "Lord Captain"
# {petName} is the name the player gave their pet, which is a raven or a (cybernetic) dog depending on the player's
# choice; the two pets have separate lines. No name exists in the data and the audio is baked, so the placeholder is
# spoken as a noun picked from the line's own wording, and as "your pet" when the line does not say.
PET_RAVEN = re.compile(r"\b(raven|bird|feathers?|beak|croak\w*|wings?|talons?|perch)\b", re.I)
PET_DOG = re.compile(r"\b(dog|hound|mastiff|tail|wag\w*|all fours|growl\w*|paws?|fangs?|snout|jaws?|bark\w*|mauled|servo-protocols?|visors?)\b", re.I)


def pet_noun(line: str) -> str:
    raven, dog = bool(PET_RAVEN.search(line)), bool(PET_DOG.search(line))
    return "the raven" if raven and not dog else "the dog" if dog and not raven else "your pet"


def _tag_open_sub(m: re.Match) -> str:
    kind, arg = m.group(1).lower(), m.group(2)
    if kind == "petname":
        before = re.sub(r"\{[^}]*\}|<[^>]*>", "", m.string[:m.start()])
        noun = pet_noun(re.sub(r"\{[^}]*\}|<[^>]*>", "", m.string))
        return noun[0].upper() + noun[1:] if re.search(r"(^|[.!?…:]['\"”)]*)\s*$", before) else noun
    if kind == "name":
        return PLAYER_ADDRESS
    if kind == "mf" and arg:  # {mf|male|female} gender variant - keep the first form
        return arg.split("|")[0]
    return ""  # {g|..}, {d}, {nc}, {br} etc. wrap/format visible text; carries nothing to speak


def speech_only(text: str) -> str:
    """Drop narration segments, keep quoted/spoken text, strip markup and quotes."""
    t = NARR_SEG.sub(" ", text)
    t = TAG_OPEN.sub(_tag_open_sub, t)
    t = TAG_CLOSE.sub("", t)
    t = re.sub(r"\s*—\s*", ", ", t).replace('"', " ")  # absorb spaces around the dash, else "a — b" gives "a , b"
    return re.sub(r"\s+", " ", t).strip()


def narration_only(text: str) -> str:
    t = TAG_OPEN.sub(_tag_open_sub, text)
    t = TAG_CLOSE.sub("", t)
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
