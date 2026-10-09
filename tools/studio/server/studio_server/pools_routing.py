from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools/npc_profile"))
from known import build_known, match  # noqa: E402,F401  (build_known is re-exported for pools.py)

NARRATOR_ID = "NARRATOR"
DEFAULT_THRESHOLD = 0.8
UNKNOWN = "unknown"


def entry_key(conversation: str, roster_id: str) -> str:
    """The key match_review.py uses in match_decisions.json. The conversation name is used exactly as stored."""
    return f"{conversation}|{roster_id}"


def _slot_route(attr: dict, entry: str | None, confidence: float | None, reasons: list[str]) -> dict:
    return {"to": "slot", "attr": attr, "entry": entry, "confidence": confidence, "reasons": reasons, "source": "auto"}


def _unknown_attr() -> dict:
    return {"gender": UNKNOWN, "species": "human", "age": UNKNOWN}


def _slot_reasons(x: dict, line_conf: float | None, threshold: float) -> list[str]:
    """Only the axes that change which voice a line gets. Unknown age is not a reason; low FX confidence is not either."""
    reasons = []
    if line_conf is not None and line_conf < threshold:
        reasons.append("line attribution")
    conf = x.get("conf") or {}
    if (x.get("gender") or UNKNOWN) == UNKNOWN:
        reasons.append("gender unknown")
    elif conf.get("gender", 1.0) < threshold:
        reasons.append("gender low confidence")
    if (x.get("species") or UNKNOWN) == UNKNOWN:
        reasons.append("species unknown")
    elif conf.get("species", 1.0) < threshold:
        reasons.append("species low confidence")
    return reasons


def _route_entry(key: str, x: dict, line_conf: float | None, known: dict, decisions: dict, threshold: float,
                 memo: dict) -> dict:
    verdict = decisions.get(key)
    if key not in memo:
        memo[key] = None if verdict == "reject" else match(x, known)
    m = memo[key]
    if m:
        reasons = ["ambiguous match"] if verdict != "accept" and (m.get("ambiguous_with") or m.get("warning")) else []
        return {"to": "speaker", "speaker": m["speaker"], "has_bank": bool(m["has_bank"]), "entry": key,
                "confidence": line_conf, "reasons": reasons, "source": "auto"}
    attr = {"gender": x.get("gender") or UNKNOWN, "species": x.get("species") or UNKNOWN, "age": x.get("age") or UNKNOWN}
    return _slot_route(attr, key, line_conf, _slot_reasons(x, line_conf, threshold))


def route_lines(guids: set[str], roster: list[dict], known: dict, decisions: dict,
                threshold: float = DEFAULT_THRESHOLD) -> dict[str, dict]:
    routes: dict[str, dict] = {}
    memo: dict = {}
    for conv in roster:
        entries = {x["id"]: x for x in conv["roster"]}
        for ln in conv["lines"]:
            guid = ln["key"]
            if guid not in guids or guid in routes:
                continue
            line_conf = (ln.get("conf") or {}).get("speaker")
            sid = ln["speaker"]
            if sid == NARRATOR_ID:
                routes[guid] = {"to": "narrator", "entry": None, "confidence": line_conf, "reasons": [], "source": "auto"}
            elif sid not in entries:
                routes[guid] = _slot_route(_unknown_attr(), None, line_conf, ["no roster entry"])
            else:
                routes[guid] = _route_entry(entry_key(conv["conversation"], sid), entries[sid], line_conf, known,
                                            decisions, threshold, memo)
    for guid in guids - routes.keys():
        routes[guid] = _slot_route(_unknown_attr(), None, None, ["not in roster"])
    return routes
