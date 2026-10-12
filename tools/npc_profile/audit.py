"""Decide which conversations a human (or the bigger model) should look at.

audit(result) combines two things: the model's own probability for each decided field (confidence.py) and a few
rule flags that catch mistakes a confident model still makes. `threshold` is tunable: anything with a field
probability below it, or any rule flag, puts the conversation on the audit list.
"""
from __future__ import annotations

from roster import NARRATOR

# Fields whose low probability matters, with how strict each is relative to `threshold`. Gender and who-speaks-what change
# the voice a lot; age barely does and species is often a judgement call, so they only trip the audit when quite unsure.
# 'unknown' answers are handled by the rules below instead.
FIELD_SCALE = {"gender": 1.0, "species": 0.75, "age": 0.3}
ROSTER_FIELDS = tuple(FIELD_SCALE)


def audit(result: dict, threshold: float = 0.8) -> dict:
    reasons: list[str] = []
    lows: list[float] = []
    for r in result["roster"]:
        who = r.get("name") or r.get("label") or r["id"]
        conf = r.get("conf", {})
        for f in ROSTER_FIELDS:
            p = conf.get(f)
            if p is not None and r[f] != "unknown" and p < threshold * FIELD_SCALE[f]:
                reasons.append(f"{who}: {f}={r[f]} p={p:.2f}")
                lows.append(p)
        if r.get("gender_source") == "pronouns":
            reasons.append(f"{who}: gender from pronoun count only")
        if r["gender"] == "unknown" and r["species"] != "machine":
            reasons.append(f"{who}: gender unknown")
    for a in result["lines"]:
        p = a.get("conf", {}).get("speaker")
        if a["speaker"] == "unknown":
            reasons.append(f"line {a['n']}: speaker unknown")
        elif a["speaker"] != NARRATOR and p is not None and p < threshold:
            reasons.append(f"line {a['n']}: speaker={a['speaker']} p={p:.2f}")
            lows.append(p)
    speakers = {r["id"] for r in result["roster"]}
    unnamed = [r for r in result["roster"] if not r["name"]]
    if len(unnamed) >= 2:
        reasons.append(f"{len(unnamed)} unnamed speakers in one conversation")
    if len(speakers) >= 3:
        reasons.append(f"{len(speakers)} speakers in one conversation")
    return {"score": round(min(lows), 3) if lows else 1.0, "reasons": reasons, "needs_review": bool(reasons)}
