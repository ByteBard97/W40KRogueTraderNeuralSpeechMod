"""GET /api/summary: the numbers the shell badges need, in one cheap call.

Every section except `speakers` can be missing (its data is not built yet or its source file is unreadable); a missing
section is null and never fails the call. The expensive ones (matches, qa) are cached on the mtimes of their inputs.
"""
from __future__ import annotations

from pathlib import Path

from . import jobs, matches, pools, qa, speakers
from .config import Config
from .errors import ApiError
from .jsonio import read_json

_CACHE: dict[tuple, tuple[tuple, object]] = {}


def _stamp(*paths: Path) -> tuple:
    return tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in paths)


def _cached(cfg: Config, name: str, stamp: tuple, build):
    key = (str(cfg.root), name)
    hit = _CACHE.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    val = build()
    _CACHE[key] = (stamp, val)
    return val


def _speakers_block(cfg: Config) -> dict:
    sp = speakers.list_speakers(cfg)
    designed = [s for s in sp if s["origin"] == "designed"]
    return {"total": len(sp), "needs_voice": sum(s["status"] == "needs_voice" for s in sp),
            "picked": sum(bool(s["pick"]) for s in designed), "registered": sum(bool(s["registered"]) for s in sp)}


def _pools_block(cfg: Config) -> dict | None:
    try:
        s = pools.summary(cfg)
    except ApiError:
        return None                       # 404: not built yet
    return {"built": s["built"], "total": s["total"], "queue_entries": s["queue_entries"],
            "queue_lines": s["queue_lines"]}


def _matches_block(cfg: Config) -> dict | None:
    def build():
        decided = matches.decisions(cfg)
        rows = matches.rows(cfg)
        flagged = [r for r in rows if r["flagged"]]
        return {"total": len(rows), "flagged": len(flagged),
                "flagged_unreviewed": sum(not decided.get(r["id"]) for r in flagged),
                "reviewed": sum(bool(decided.get(r["id"])) for r in rows),
                "accepted": sum(decided.get(r["id"]) == "accept" for r in rows),
                "rejected": sum(decided.get(r["id"]) == "reject" for r in rows),
                "undecided": sum(matches.effective(r, decided) == "" for r in rows)}
    try:
        stamp = _stamp(cfg.root / pools.ROSTER, cfg.root / pools.CONVERSATIONS, cfg.root / pools.DECISIONS,
                       cfg.voices / "prompts/prompts.json", cfg.render / "jobs.jsonl")
        return _cached(cfg, "matches", stamp, build)
    except Exception:               # a broken source must not take the whole summary down
        return None


def _qa_block(cfg: Config) -> dict | None:
    try:
        clips = qa.clips(cfg, qa.EXPORT)
        judged = qa.get_verdicts(cfg, qa.EXPORT)
        stamp = (id(clips), len(judged)) + _stamp(qa._verdicts_path(cfg, qa.EXPORT))

        def build():
            guids = {c["guid"] for c in clips}
            good = sum(1 for g, v in judged.items() if g in guids and v.get("verdict") == "good")
            bad = sum(1 for g, v in judged.items() if g in guids and v.get("verdict") == "bad")
            return {"run": qa.EXPORT, "total": len(clips), "good": good, "bad": bad, "unjudged": len(clips) - good - bad}
        return _cached(cfg, "qa", stamp, build)
    except Exception:
        return None


def summary(cfg: Config, model) -> dict:
    sp = _speakers_block(cfg)
    return {"speakers_left": sp["needs_voice"], "speakers": sp, "pools": _pools_block(cfg),
            "matches": _matches_block(cfg), "qa_clips": _qa_block(cfg), "model": jobs.health(cfg, model)}
