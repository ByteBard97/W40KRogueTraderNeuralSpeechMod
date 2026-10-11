from __future__ import annotations

import json
import threading
from collections import defaultdict

from . import pools
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .pools_routing import entry_key, match

SAMPLE_LINES = 3
DEFAULT_LIMIT = 50
MAX_PAGE = 200
SAMPLE_CHARS = 600
VALUES = ("", "accept", "reject")
STATES = ("undecided", "unreviewed", "reviewed", "accept", "reject")
REBUILD_DEBOUNCE_S = 3.0
PROMPTS = "data/voices/prompts/prompts.json"
JOBS = "data/render/jobs.jsonl"


def decisions(cfg: Config) -> dict:
    return read_json(cfg.root / pools.DECISIONS, {})


def group_of(row: dict) -> str:
    return "flagged" if row["flagged"] else "bank" if row["has_bank"] else "nobank"


def effective(row: dict, decided: dict) -> str:
    """A clean match counts as accepted until the user says otherwise; a flagged one stays undecided."""
    stored = decided.get(row["id"], "")
    return stored or ("" if row["flagged"] else "accept")


_TEXT: dict = {}     # not speakers._cached: pools._known already caches this file there under its own loader


def _line_text(cfg: Config) -> dict[str, str]:
    """text_key -> line text over every conversation line (the old match_review sampled all of them)."""
    path = cfg.root / pools.CONVERSATIONS
    if not path.exists():
        return {}
    stamp = path.stat().st_mtime_ns
    hit = _TEXT.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    convs = json.loads(path.read_text(encoding="utf-8"))
    val = {ln["text_key"]: ln["text"] for cv in convs for ln in cv["lines"] if ln.get("text_key") and ln.get("text")}
    _TEXT[path] = (stamp, val)
    return val


_ROWS: dict = {}


def _stamp(cfg: Config) -> tuple:
    return tuple(p.stat().st_mtime_ns if p.exists() else 0
                 for p in (cfg.root / pools.ROSTER, cfg.root / pools.CONVERSATIONS, cfg.root / PROMPTS, cfg.root / JOBS))


def speaker_sample(cfg: Config, speaker: str) -> str | None:
    """Repo path of the first prompt-bank clip of a banked speaker, so the match can be auditioned."""
    for p in read_json(cfg.root / PROMPTS, {}).get(speaker) or []:
        rel = f"data/voices/{p.get('wav', '')}"
        if p.get("wav") and (cfg.root / rel).is_file():
            return rel
    return None


def suggestion(row: dict) -> tuple[str, str]:
    """accept/reject with a reason. A match warning means the text contradicts the game's gender tag on few lines:
    reject. Everything else, including homonyms, accepts."""
    if row["warning"]:
        return "reject", str(row["warning"])[:1].upper() + str(row["warning"])[1:] + "."
    if row["ambiguous_with"]:
        also = ", ".join(row["ambiguous_with"])
        return "accept", f"Also matches {also}." + (f" Accepting uses the {row['speaker']} bank." if row["has_bank"] else "")
    return "accept", ""


def rows(cfg: Config) -> list[dict]:
    """Every match, cached until the roster, conversations, prompt bank or jobs file changes. Do not mutate the result."""
    key, stamp = str(cfg.root), _stamp(cfg)
    hit = _ROWS.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    val = _build_rows(cfg)
    _ROWS[key] = (stamp, val)
    return val


def _build_rows(cfg: Config) -> list[dict]:
    roster, known = pools._roster(cfg), pools._known(cfg)
    text = {j["guid"]: j["text"] for j in pools._unnamed_jobs(cfg)}
    text.update(_line_text(cfg))
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
                "role": e.get("role"), "evidence": list(e.get("evidence") or []), "lines": len(keys),
                "samples": [text.get(k, "")[:SAMPLE_CHARS] for k in keys[:SAMPLE_LINES]],
                "gaps": [pairs[i + 1][1] - pairs[i][1] > 1 for i in range(min(len(pairs), SAMPLE_LINES) - 1)],
                "speaker": m["speaker"], "has_bank": bool(m["has_bank"]), "speaker_lines": m["lines"],
                "game_gender": m["game_gender"], "warning": m.get("warning"), "ambiguous_with": m.get("ambiguous_with"),
                "flagged": bool(m.get("warning") or m.get("ambiguous_with")),
            })
            out[-1]["suggest"], out[-1]["suggest_reason"] = suggestion(out[-1])
            out[-1]["speaker_sample"] = speaker_sample(cfg, m["speaker"]) if m["has_bank"] else None
    out.sort(key=lambda r: (not r["flagged"], not r["has_bank"], r["speaker"], r["conversation"]))
    return out


def page(cfg: Config, *, group=None, speaker=None, state=None, q=None, offset=0, limit=DEFAULT_LIMIT) -> dict:
    if state and state not in STATES:
        raise ApiError(400, f"state must be one of {STATES}")
    decided = decisions(cfg)
    everything = [{**r, "decision": decided.get(r["id"], ""), "effective": effective(r, decided)} for r in rows(cfg)]
    counts = {"flagged": 0, "bank": 0, "nobank": 0, "undecided": 0, "total": len(everything), "accepted": 0,
              "rejected": 0, "reviewed": 0, "unreviewed": 0, "flagged_unreviewed": 0}
    for r in everything:
        counts[group_of(r)] += 1
        counts["undecided"] += r["effective"] == ""
        counts["accepted"] += r["decision"] == "accept"
        counts["rejected"] += r["decision"] == "reject"
        counts["flagged_unreviewed"] += r["flagged"] and not r["decision"]
    counts["reviewed"] = counts["accepted"] + counts["rejected"]
    counts["unreviewed"] = counts["total"] - counts["reviewed"]
    want = (q or "").lower()
    shown = []
    for r in everything:
        if group and group_of(r) != group or speaker and speaker.lower() not in r["speaker"].lower():
            continue
        if state == "unreviewed" and r["decision"] or state == "reviewed" and not r["decision"]:
            continue
        if state in ("undecided", "accept", "reject") and (r["effective"] or "undecided") != state:
            continue
        if want and want not in " ".join([r["name"] or "", r["label"] or "", r["speaker"], *r["samples"]]).lower():
            continue
        shown.append(r)
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    return {"total": len(shown), "offset": offset, "limit": limit, "counts": counts, "items": shown[offset:offset + limit],
            "pools_stale": pools_stale(cfg)}


def pools_stale(cfg: Config) -> bool:
    """True when a decision was saved after the pools were last built (a deferred rebuild is pending)."""
    dec, built = cfg.root / pools.DECISIONS, pools.pools_path(cfg)
    return dec.exists() and built.exists() and dec.stat().st_mtime_ns > built.stat().st_mtime_ns


_TIMERS: dict = {}


def flush_pools(cfg: Config) -> dict:
    """Rebuild the pools if decisions changed since the last build. Cheap when nothing is pending."""
    with STATE_LOCK:
        if not pools_stale(cfg):
            return {"pools_rebuilt": False, "pools_stale": False}
        return {"pools_rebuilt": True, "pools_stale": False, "queue_entries": pools.rebuild(cfg)["queue_entries"]}


def _schedule_flush(cfg: Config) -> None:
    """Debounce: a burst of decisions rebuilds once, REBUILD_DEBOUNCE_S after the last one."""
    def run():
        try:
            flush_pools(cfg)
        except Exception:        # the temp repo may be gone, or a rebuild may fail; the next pools read retries
            pass
    key = str(cfg.root)
    with STATE_LOCK:
        old = _TIMERS.pop(key, None)
        if old:
            old.cancel()
        t = _TIMERS[key] = threading.Timer(REBUILD_DEBOUNCE_S, run)
        t.daemon = True
        t.start()


def save(cfg: Config, rid: str, value: str, rebuild: bool = True) -> dict:
    """rebuild=True (default) rebuilds the pools now; False defers: the rebuild runs after a pause, on POST
    /api/matches/rebuild, or before the next pools read, whichever comes first."""
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
    if not rebuild:
        _schedule_flush(cfg)
        return {"pools_rebuilt": False, "pools_stale": True}
    return {"pools_rebuilt": True, "queue_entries": pools.rebuild(cfg)["queue_entries"]}
