"""Does a learned weighting of the free metrics pick takes the user rated higher than the equal-weight composite?

Leave-one-LINE-out (the held-out line's takes never influence the weights). Score for a line = mean rating of
the take each method picks minus the line's mean rating. CPU only; reads existing metrics/ratings.
  python3 tools/scorer/probe_learned_weights.py [--axis voice]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge

from selection import VOICE_FEATURES

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / "data/bakeoff_abelard_cfg_sweep"
EXTRA = ("wer", "trail", "lead", "rms", "chars_per_sec")


def load(axis):
    m = json.load(open(ROOT / "data/scorer_probe/metrics.json"))
    r = json.load(open(SWEEP / "ratings.json"))
    man = {x["cell_id"]: x for x in json.load(open(SWEEP / "manifest.json"))}
    lines = defaultdict(list)
    for c in man:
        if c in m and c in r and axis in r[c] and all(np.isfinite(m[c][f]) for f in VOICE_FEATURES + EXTRA):
            lines[man[c]["guid"]].append(c)
    return m, r, {g: cs for g, cs in lines.items() if len(cs) >= 3}


def within_line_center(X, y, groups):
    Xc, yc = X.copy(), y.copy()
    for g in set(groups):
        i = [k for k, x in enumerate(groups) if x == g]
        Xc[i] -= Xc[i].mean(0)
        yc[i] -= yc[i].mean()
    return Xc, yc


def run(axis, feats, alpha):
    m, r, lines = load(axis)
    guids = sorted(lines)
    gains, base_gains = [], []
    for held in guids:
        train = [c for g in guids if g != held for c in lines[g]]
        X = np.array([[m[c][f] for f in feats] for c in train], float)
        y = np.array([r[c][axis] for c in train], float)
        groups = [next(g for g in guids if c in lines[g]) for c in train]
        mu, sd = X.mean(0), X.std(0)
        Xc, yc = within_line_center((X - mu) / sd, y, groups)
        w = Ridge(alpha=alpha, fit_intercept=False).fit(Xc, yc).coef_
        cs = lines[held]
        Xh = (np.array([[m[c][f] for f in feats] for c in cs], float) - mu) / sd
        h = np.array([r[c][axis] for c in cs], float)
        gains.append(h[np.argmax(Xh @ w)] - h.mean())
        Xe = np.array([[m[c][f] for f in VOICE_FEATURES] for c in cs], float)
        Xe = (Xe - X[:, :5].mean(0)) / X[:, :5].std(0) if feats[:5] == VOICE_FEATURES else Xe
    return np.array(gains), len(guids)


def equal_weight(axis):
    m, r, lines = load(axis)
    allX = np.array([[m[c][f] for f in VOICE_FEATURES] for cs in lines.values() for c in cs], float)
    sd = allX.std(0)
    out = []
    for cs in lines.values():
        h = np.array([r[c][axis] for c in cs], float)
        s = np.array([[m[c][f] for f in VOICE_FEATURES] for c in cs], float) @ (1 / sd)
        out.append(h[np.argmax(s)] - h.mean())
    return np.array(out)


def boot(x, n=5000, seed=0):
    rng = np.random.default_rng(seed)
    b = [rng.choice(x, len(x)).mean() for _ in range(n)]
    return np.percentile(b, [2.5, 97.5])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--axis", default="voice")
    a = ap.parse_args()
    eq = equal_weight(a.axis)
    lo, hi = boot(eq)
    print(f"{a.axis}: equal-weight composite gain {eq.mean():+.2f} (95% CI {lo:+.2f}..{hi:+.2f}, {len(eq)} lines)")
    for name, feats in (("5 voice features", VOICE_FEATURES), ("voice + extras", VOICE_FEATURES + EXTRA)):
        for alpha in (1.0, 10.0, 100.0):
            g, n = run(a.axis, list(feats), alpha)
            lo, hi = boot(g)
            print(f"  learned ridge {name}, alpha={alpha:g}: gain {g.mean():+.2f} (95% CI {lo:+.2f}..{hi:+.2f}); "
                  f"paired vs equal {np.mean(g - eq):+.2f}")
