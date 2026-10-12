"""Agreement between automated pickers and the human's blind A/B answers (stdlib only).

A picker is anything that says 'a' or 'b' per pair id (the free scorer's `scorer_prefers`, or the
audio-LLM judge's consistent verdicts). Ties and unanswered pairs are excluded from agreement.
"""
from __future__ import annotations

import math


def binom_p_greater(k: int, n: int, p: float = 0.5) -> float:
    """One-sided exact P(X >= k) for X ~ Binomial(n, p)."""
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1)) if n else 1.0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def agreement(pairs: list[dict], answers: dict[str, str], picks: dict[str, str | None]) -> dict[str, dict]:
    out = {}
    for axis in sorted({p["axis"] for p in pairs}):
        ids = [p["id"] for p in pairs if p["axis"] == axis and p["id"] in answers]
        dec = [i for i in ids if answers[i] in ("a", "b")]
        used = [i for i in dec if picks.get(i) in ("a", "b")]
        k = sum(picks[i] == answers[i] for i in used)
        lo, hi = wilson(k, len(used))
        out[axis] = {"answered": len(ids), "ties": len(ids) - len(dec), "decisive": len(dec), "picker_covered": len(used),
                     "agree": k, "rate": k / len(used) if used else None, "ci95": (lo, hi) if used else None,
                     "p_vs_coin": binom_p_greater(k, len(used))}
    return out


def render(name: str, res: dict[str, dict]) -> str:
    lines = [f"== {name} =="]
    for axis, r in res.items():
        if r["rate"] is None:
            lines.append(f"{axis}: {r['answered']} answered, nothing comparable yet")
            continue
        lo, hi = r["ci95"]
        lines.append(f"{axis}: agrees {r['agree']}/{r['picker_covered']} = {r['rate']:.0%} (95% CI {lo:.0%}-{hi:.0%}, "
                     f"p={r['p_vs_coin']:.3f} vs coin flip); {r['ties']} ties of {r['answered']} answered")
    return "\n".join(lines)
