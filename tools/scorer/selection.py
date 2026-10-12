"""Pure take-selection logic (numpy only, no models): gates, voice composite, winners, retake plan.

Kept separate from scorer.py so it can be unit-tested and run in any env.
Rows are the per-take score dicts written by Character.score() into scores.jsonl.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CAL = ROOT / "data/scorer_probe/calibration.json"

VOICE_FEATURES = ("ecapa_ref", "wavlm_ref", "wavlm_cent", "ecapa_cent", "utmos")
WER_GATE = 0.34
MAX_TRAIL_SILENCE = 1.5
LOW_EMOTION_P = 0.10
FEW_CANDIDATES = 3


def calibration() -> dict:
    """Per-feature std over the 228 hand-rated sweep clips (scale for the composite)."""
    if not CAL.exists():
        m = json.load(open(ROOT / "data/scorer_probe/metrics.json"))
        cal = {f: float(np.std([v[f] for v in m.values()])) for f in VOICE_FEATURES}
        json.dump(cal, open(CAL, "w"), indent=1)
    return json.load(open(CAL))


def voice_composite(rows: list[dict], scale: dict[str, float]) -> np.ndarray:
    """Sum of per-feature values divided by a fixed per-feature scale (stds measured on the
    228-clip sweep, calibration.json). Ranking only: compare takes of the same line."""
    return sum(np.array([r[f] for r in rows]) / scale[f] for f in VOICE_FEATURES)


def passes_gates(row: dict) -> bool:
    return (row.get("wer", 0) <= WER_GATE and not row["clipped"]
            and row["trail_silence"] <= MAX_TRAIL_SILENCE)


def take_key(guid: str, take: int) -> str:
    return f"{guid}#{take}"


def select_winners(manifest: list[dict], scores: dict[str, dict], scale: dict[str, float]) -> dict[str, dict]:
    """Best passing take per line. Lines with no passing take get status no_passing_take."""
    by_line: dict[str, list[dict]] = {}
    for m in manifest:
        if take_key(m["guid"], m["take"]) in scores:
            by_line.setdefault(m["guid"], []).append(m)
    winners = {}
    for guid, ms in by_line.items():
        rows = [scores[take_key(m["guid"], m["take"])] for m in ms]
        ok = [i for i, r in enumerate(rows) if passes_gates(r)]
        entry = {"n_takes": len(ms), "n_pass": len(ok), "text": ms[0]["text"], "emotion": ms[0]["emotion"]}
        if not ok:
            entry.update(status="no_passing_take", flags=["needs_more_takes"])
        else:
            vc = voice_composite(rows, scale)
            best = max(ok, key=lambda i: vc[i])
            r = rows[best]
            flags = []
            if len(ok) < FEW_CANDIDATES:
                flags.append("few_candidates")
            p = r.get("p_target_family")
            if p is not None and p < LOW_EMOTION_P:
                flags.append("low_emotion_prob")
            entry.update(status="ok", take=ms[best]["take"], wav=ms[best]["wav"], voice_score=float(vc[best]),
                         voice_score_spread=float(np.ptp(vc[ok])), p_target_family=p,
                         target_family=r.get("target_family"), wer=r.get("wer"), flags=flags)
        winners[guid] = entry
    return winners


def plan_retakes(winners: dict[str, dict], all_guids: list[str], min_pass: int, max_takes: int) -> list[str]:
    """Lines that still need more takes: unscored lines, and lines with fewer than min_pass
    passing takes, unless they already hit max_takes."""
    need = []
    for guid in all_guids:
        w = winners.get(guid)
        if w is None:
            need.append(guid)
        elif w["n_pass"] < min_pass and w["n_takes"] < max_takes:
            need.append(guid)
    return need


def review_queue(winners: dict[str, dict], min_spread: float = 0.5) -> list[dict]:
    """Lines a human should listen to: nothing passed, a weak emotion match, or the winner is
    not clearly better than the runner-up field (small spread with few candidates)."""
    out = []
    for guid, w in winners.items():
        reasons = []
        if w["status"] != "ok":
            reasons.append("no_passing_take")
        else:
            if "low_emotion_prob" in w["flags"]:
                reasons.append("low_emotion_prob")
            if "few_candidates" in w["flags"]:
                reasons.append("few_candidates")
            if w["n_pass"] > 1 and w["voice_score_spread"] < min_spread:
                reasons.append("takes_indistinguishable")
        if reasons:
            out.append({"guid": guid, "text": w["text"], "emotion": w["emotion"], "reasons": reasons,
                        "wav": w.get("wav")})
    return out
