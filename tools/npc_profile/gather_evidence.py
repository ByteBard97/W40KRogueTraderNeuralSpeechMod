#!/usr/bin/env python3
"""Collect the text evidence an LLM needs to describe one named NPC's voice.

For each priority-3 speaker (jobs.jsonl) this writes data/npc_profile/evidence/<slug>.json with:
  facts       game data: gender, race, blueprint names (ground truth, not for the LLM to guess)
  own_lines   a spread of the NPC's own spoken lines
  narration   narrator cues from the NPC's conversations that mention them (appearance, manner)
  mentions    other characters' lines that name them
and a ready-to-send `prompt_text` capped at --max-chars.

Usage: python3 tools/npc_profile/gather_evidence.py [--min-lines 1] [--max-chars 9000] [--only NAME]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/npc_profile/evidence"
TITLE_WORDS = {"master", "high", "vox", "lord", "lady", "captain", "the", "of", "von", "vedka", "magos",
               "archmachinator", "factotum", "helmsman", "liege", "cruel", "infinite"}

_MF = re.compile(r"\{mf\|([^|}]*)\|[^}]*\}")
_TAG = re.compile(r"\{/?[a-z]+(?:\|[^}]*)?\}|<[^>]+>")


def clean(t: str) -> str:
    t = _MF.sub(r"\1", t)  # {mf|Lordship|Ladyship} -> Lordship
    t = _TAG.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def name_keys(name: str) -> list[str]:
    """Distinctive tokens others would use to refer to this NPC (surname/given name, not titles)."""
    toks = [t for t in re.findall(r"[A-Za-z'\-]+", name) if len(t) >= 4 and t.lower() not in TITLE_WORDS]
    return toks or [name]


def spread(items: list, n: int) -> list:
    """n items evenly spaced through the list (keeps early and late lines)."""
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-lines", type=int, default=1)
    ap.add_argument("--max-chars", type=int, default=9000)
    ap.add_argument("--only")
    args = ap.parse_args()

    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    jobs = [json.loads(ln) for ln in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines()]
    counts = Counter(j["speaker"] for j in jobs if j["priority"] == 3 and j["speaker"] != "default_speaker")
    targets = [n for n, c in counts.items() if c >= args.min_lines and (not args.only or n == args.only)]

    facts: dict[str, dict] = {n: {"gender": Counter(), "race": Counter(), "blueprints": Counter(), "lines": 0} for n in targets}
    own: dict[str, list] = defaultdict(list)
    narr: dict[str, list] = defaultdict(list)
    ment: dict[str, list] = defaultdict(list)
    keys = {n: [re.compile(r"\b" + re.escape(k) + r"\b") for k in name_keys(n)] for n in targets}

    for cv in convs:
        speakers_here = set()
        for ln in cv["lines"]:
            s = ln.get("speaker") or {}
            if s.get("kind") == "unit" and s.get("name") in facts:
                f = facts[s["name"]]
                f["gender"][s.get("gender")] += 1
                f["race"][s.get("race")] += 1
                f["blueprints"][s.get("blueprint")] += 1
                speakers_here.add(s["name"])
        for ln in cv["lines"]:
            text = ln.get("text")
            if not text or ln.get("kind") != "cue":
                continue
            s = ln.get("speaker") or {}
            t = clean(text)
            if s.get("kind") == "unit" and s.get("name") in facts:
                facts[s["name"]]["lines"] += 1
                own[s["name"]].append(t)
            for n in targets:
                if s.get("name") == n:
                    continue
                if any(k.search(t) for k in keys[n]):
                    if s.get("kind") == "narrator":
                        narr[n].append(t)
                    elif n in speakers_here:  # only lines from conversations the NPC is actually in
                        ment[n].append(f"{s.get('name') or s.get('kind')}: {t}")

    OUT.mkdir(parents=True, exist_ok=True)
    for n in targets:
        f = facts[n]
        rec = {
            "name": n,
            "facts": {"gender": f["gender"].most_common(1)[0][0] if f["gender"] else None,
                      "race": f["race"].most_common(1)[0][0] if f["race"] else None,
                      "blueprints": [b for b, _ in f["blueprints"].most_common(4)],
                      "spoken_lines": f["lines"], "unvoiced_lines": counts[n]},
            "own_lines": spread(own[n], 14),
            "narration": spread(list(dict.fromkeys(narr[n])), 10),
            "mentions": spread(list(dict.fromkeys(ment[n])), 8),
        }
        rec["prompt_text"] = render(rec, args.max_chars)
        (OUT / f"{slug(n)}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(targets)} evidence files to {OUT}")


def render(rec: dict, cap: int) -> str:
    fx = rec["facts"]
    head = (f"Character: {rec['name']}\nGame data (certain): gender={fx['gender']}, race={fx['race'] or 'human (unspecified)'}, "
            f"role ids={', '.join(b for b in fx['blueprints'] if b)}\n")
    parts = [("Narration that mentions them", rec["narration"]), ("Other characters talking about them", rec["mentions"]),
             ("Their own lines", rec["own_lines"])]
    out = head
    for title, items in parts:
        block = f"\n## {title}\n" + "".join(f"- {i[:420]}\n" for i in items) if items else f"\n## {title}\n(none found)\n"
        if len(out) + len(block) > cap:
            block = block[: max(0, cap - len(out))]
        out += block
    return out


if __name__ == "__main__":
    sys.exit(main())
