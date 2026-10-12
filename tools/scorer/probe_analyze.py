"""THROWAWAY PROBE analysis: do automatic metrics track the user's 228 hand ratings?"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau, spearmanr
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / "data/bakeoff_abelard_cfg_sweep"
metrics = json.load(open(ROOT / "data/scorer_probe/metrics.json"))
ratings = json.load(open(SWEEP / "ratings.json"))
tags = json.load(open(SWEEP / "tags.json"))
manifest = {m["cell_id"]: m for m in json.load(open(SWEEP / "manifest.json"))}

ids = [c for c in manifest if c in metrics and c in ratings]
print(f"{len(ids)} clips with metrics and ratings")

for c in ids:
    m = metrics[c]
    m["ad_dist"] = float(np.hypot(m["arousal"] - m["ref_arousal"], m["dominance"] - m["ref_dominance"]))
    m["avd_dist"] = float(np.sqrt(sum((m[k] - m["ref_" + k]) ** 2 for k in ("arousal", "dominance", "valence"))))
    m["arousal_gap"] = m["arousal"] - m["ref_arousal"]
    m["abs_arousal_gap"] = abs(m["arousal_gap"])
    m["abs_dur_dev"] = abs(m["chars_per_sec"] - 14.0)  # crude speech-rate outlier proxy

FEATS = ["wavlm_ref", "wavlm_cent", "ecapa_ref", "ecapa_cent", "utmos", "wer", "wer_masked",
         "ad_dist", "avd_dist", "abs_arousal_gap", "arousal", "dominance", "valence",
         "chars_per_sec", "lead", "trail", "peak", "rms", "dur"]
lines = defaultdict(list)
for c in ids:
    lines[manifest[c]["guid"]].append(c)

def col(f, cs=None):
    return np.array([metrics[c][f] for c in (cs or ids)], dtype=float)

def per_line(f, axis):
    taus, top1, base = [], [], []
    for g, cs in lines.items():
        cs = [c for c in cs if axis in ratings[c]]
        if len(cs) < 3:
            continue
        h = np.array([ratings[c][axis] for c in cs], float)
        v = np.array([metrics[c][f] for c in cs], float)
        if np.ptp(h) == 0 or np.ptp(v) == 0 or not np.isfinite(v).all():
            continue
        taus.append(kendalltau(v, h)[0])
        top1.append(float(h[np.argmax(v)] == h.max()))
        base.append(float((h == h.max()).mean()))
    return np.mean(taus), np.mean(top1), np.mean(base), len(taus)

for axis in ("voice", "emotion"):
    aids = [c for c in ids if axis in ratings[c]]
    y = np.array([ratings[c][axis] for c in aids], float)
    print(f"\n=== {axis} (n={len(aids)}) rating (higher = better) | global rho, per-line tau, top1 vs random ===")
    rows = []
    for f in FEATS:
        x = col(f, aids)
        ok = np.isfinite(x)
        rho = spearmanr(x[ok], y[ok])[0]
        t, t1, b1, n = per_line(f, axis)
        rows.append((abs(rho), f, rho, t, t1, b1, n))
    for _, f, rho, t, t1, b1, n in sorted(rows, reverse=True):
        print(f"{f:18s} rho={rho:+.2f}  line_tau={t:+.2f}  top1={t1:.2f} (random {b1:.2f}, {n} lines)")

# failure-tag AUROC, only on lines from the tag era (any clip tagged) so "untagged" means clean
tag_lines = {manifest[c]["guid"] for c in tags if c in manifest}
era = [c for c in ids if manifest[c]["guid"] in tag_lines]
print(f"\n=== tag AUROC (tag-era lines only: {len(era)} clips) ===")
for tag in ["gravelly", "whisper", "too high", "rhotic R", "rushed", "other"]:
    yy = np.array([tag in tags.get(c, []) for c in era])
    if yy.sum() < 3 or yy.all():
        print(f"{tag}: only {yy.sum()} positives, skipped")
        continue
    res = []
    for f in FEATS:
        x = np.array([metrics[c][f] for c in era], float)
        if not np.isfinite(x).all():
            continue
        a = roc_auc_score(yy, x)
        res.append((max(a, 1 - a), f, a))
    top = sorted(res, reverse=True)[:4]
    print(f"{tag} (n={int(yy.sum())}): " + ", ".join(f"{f} {a:.2f}" for _, f, a in top))

# does cfg explain the same thing? sanity check that metrics see the known cfg effect
print("\n=== mean metric by cfg (sanity: user found voice score rises with cfg) ===")
by = defaultdict(list)
for c in ids:
    by[manifest[c]["cfg_value"]].append(c)
for cfg in sorted(by):
    cs = by[cfg]
    print(f"cfg {cfg}: n={len(cs)} voice={np.mean([ratings[c]['voice'] for c in cs if 'voice' in ratings[c]]):.2f} "
          f"wavlm_cent={np.nanmean([metrics[c]['wavlm_cent'] for c in cs]):.3f} "
          f"ecapa_cent={np.nanmean([metrics[c]['ecapa_cent'] for c in cs]):.3f} "
          f"utmos={np.mean([metrics[c]['utmos'] for c in cs]):.2f}")
