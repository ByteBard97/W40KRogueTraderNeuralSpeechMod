"""Match a character the harness found in an unattributed conversation to a speaker the game already names.

Many "unnamed" lines belong to NPCs that have a name elsewhere (Ravor, Heinrix, Jae). Mapping them lets all of a
character's lines share one voice, and lets the ones with a recorded voice bank use it.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

# Words that appear in names and descriptions but do not identify a person.
STOP = {"the", "of", "von", "van", "lord", "lady", "master", "high", "vox", "captain", "sister", "brother", "reverend", "interrogator",
        "inquisitor", "tech", "priest", "magos", "first", "officer", "second", "new", "old", "young", "aggressive", "derisive",
        "calm", "angry", "sad", "frightened", "illusion", "and", "from", "with", "elder", "chief", "foreman", "artisan", "lucky"}
MIN_LINES_FOR_GENDER_VETO = 20  # the game's gender tag is unreliable on a handful of lines (Lucky Jaspar: 1 line, wrong)


def _generic(tok: str) -> bool:
    """A word, or a hyphenated word whose parts are all titles/descriptors ('tech-priest'), names nobody in particular."""
    return tok in STOP or all(part in STOP for part in tok.split("-"))


def tokens(text: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9][a-z0-9'\-]*", (text or "").lower()) if len(t) >= 3 and not _generic(t)}


def build_known(convs: list[dict], banks: set[str]) -> dict[str, dict]:
    """{speaker name: {lines, gender, has_bank, tokens}} over every named unit in the conversations."""
    acc: dict[str, dict] = defaultdict(lambda: {"lines": 0, "gender": Counter()})
    for cv in convs:
        for ln in cv["lines"]:
            sp = ln.get("speaker") or {}
            if sp.get("kind") == "unit" and sp.get("name"):
                a = acc[sp["name"]]
                a["lines"] += 1
                if sp.get("gender"):
                    a["gender"][sp["gender"].lower()] += 1
    out = {}
    for name, a in acc.items():
        out[name] = {"lines": a["lines"], "gender": a["gender"].most_common(1)[0][0] if a["gender"] else None,
                     "has_bank": name in banks, "tokens": tokens(name)}
    return out


def match(entry: dict, known: dict[str, dict]) -> dict | None:
    """Best known speaker for a roster entry, or None. Uses the entry's name; falls back to capitalised words of its label."""
    want = tokens(entry.get("name"))
    if not want:
        want = {t for t in tokens(" ".join(w for w in re.findall(r"[A-Z][A-Za-z'\-]+", entry.get("label") or "")))}
    if not want:
        return None
    best, best_score = [], 0
    for name, k in known.items():
        both = want & k["tokens"]
        # one name must contain the other: "Ravor" in "Master Helmsman Ravor", or "Theodora" in "Theodora von Valancius"
        if not both or not (want <= k["tokens"] or k["tokens"] <= want):
            continue
        if len(both) > best_score:
            best, best_score = [name], len(both)
        elif len(both) == best_score:
            best.append(name)
    if not best:
        return None
    best.sort(key=lambda n: -known[n]["lines"])
    top = best[0]
    k = known[top]
    out = {"speaker": top, "lines": k["lines"], "has_bank": k["has_bank"], "game_gender": k["gender"]}
    if len(best) > 1 and not all(known[b]["tokens"] == k["tokens"] for b in best):
        out["ambiguous_with"] = best[1:4]
    g = entry.get("gender")
    if g in ("male", "female") and k["gender"] in ("male", "female") and g != k["gender"]:
        if k["lines"] >= MIN_LINES_FOR_GENDER_VETO:
            return None  # a well-established character of the other gender is a different person
        out["warning"] = f"game tags {top} as {k['gender']} on only {k['lines']} line(s); text says {g}"
    return out
