from __future__ import annotations

from collections import defaultdict

from . import pools
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .pools_routing import entry_key, match

SAMPLE_LINES = 3
EVIDENCE_ITEMS = 3
DEFAULT_LIMIT = 50
MAX_PAGE = 200
VALUES = ("", "accept", "reject")


def decisions(cfg: Config) -> dict:
    return read_json(cfg.root / pools.DECISIONS, {})


def group_of(row: dict) -> str:
    return "flagged" if row["flagged"] else "bank" if row["has_bank"] else "nobank"


def effective(row: dict, decided: dict) -> str:
    """A clean match counts as accepted until the user says otherwise; a flagged one stays undecided."""
    stored = decided.get(row["id"], "")
    return stored or ("" if row["flagged"] else "accept")


def rows(cfg: Config) -> list[dict]:
    roster, known = pools._roster(cfg), pools._known(cfg)
    text = {j["guid"]: j["text"] for j in pools._unnamed_jobs(cfg)}
    out = []
    for conv in roster:
        mine = defaultdict(list)
        for ln in conv["lines"]:
            mine[ln["speaker"]].append((ln["key"], ln["n"]))
        for e in conv["roster"]:
            pairs = mine.get(e["id"], [])
            m = match(e, known) if pairs else None
            if not m:
                continue
            keys = [k for k, _ in pairs]
            out.append({
                "id": entry_key(conv["conversation"], e["id"]), "conversation": conv["conversation"], "entry": e["id"],
                "name": e.get("name"), "label": e.get("label"), "gender": e.get("gender"), "species": e.get("species"),
                "role": e.get("role"), "evidence": (e.get("evidence") or [])[:EVIDENCE_ITEMS], "lines": len(keys),
                "samples": [text.get(k, "") for k in keys[:SAMPLE_LINES]],
                "gaps": [pairs[i + 1][1] - pairs[i][1] > 1 for i in range(min(len(pairs), SAMPLE_LINES) - 1)],
                "speaker": m["speaker"], "has_bank": bool(m["has_bank"]), "speaker_lines": m["lines"],
                "game_gender": m["game_gender"], "warning": m.get("warning"), "ambiguous_with": m.get("ambiguous_with"),
                "flagged": bool(m.get("warning") or m.get("ambiguous_with")),
            })
    out.sort(key=lambda r: (not r["flagged"], not r["has_bank"], r["speaker"], r["conversation"]))
    return out


def page(cfg: Config, *, group=None, speaker=None, state=None, q=None, offset=0, limit=DEFAULT_LIMIT) -> dict:
    decided = decisions(cfg)
    everything = [{**r, "decision": decided.get(r["id"], ""), "effective": effective(r, decided)} for r in rows(cfg)]
    counts = {"flagged": 0, "bank": 0, "nobank": 0, "undecided": 0}
    for r in everything:
        counts[group_of(r)] += 1
        counts["undecided"] += r["effective"] == ""
    want = (q or "").lower()
    shown = []
    for r in everything:
        if group and group_of(r) != group or speaker and speaker.lower() not in r["speaker"].lower():
            continue
        if state and (r["effective"] or "undecided") != ("undecided" if state == "undecided" else state):
            continue
        if want and want not in " ".join([r["name"] or "", r["label"] or "", r["speaker"], *r["samples"]]).lower():
            continue
        shown.append(r)
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    return {"total": len(shown), "offset": offset, "limit": limit, "counts": counts, "items": shown[offset:offset + limit]}


def save(cfg: Config, rid: str, value: str) -> dict:
    if value not in VALUES:
        raise ApiError(400, f"value must be one of {VALUES}")
    if rid not in {r["id"] for r in rows(cfg)}:
        raise ApiError(404, f"no match {rid!r}")
    path = cfg.root / pools.DECISIONS
    with STATE_LOCK:
        d = read_json(path, {})
        if value:
            d[rid] = value
        else:
            d.pop(rid, None)
        write_json_atomic(path, dict(sorted(d.items())))
    if not pools.pools_path(cfg).exists():
        return {"pools_rebuilt": False}
    return {"pools_rebuilt": True, "queue_entries": pools.rebuild(cfg)["queue_entries"]}
