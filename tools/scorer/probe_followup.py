"""THROWAWAY PROBE follow-up: real tag strings, per-cfg AUROC, leave-one-line-out regret,
and the audEERING cluster test on the ear-verified reference clips."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import f_oneway
from sklearn.metrics import roc_auc_score, silhouette_score

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / "data/bakeoff_abelard_cfg_sweep"
M = json.load(open(ROOT / "data/scorer_probe/metrics.json"))
R = json.load(open(SW / "ratings.json"))
T = json.load(open(SW / "tags.json"))
man = {m["cell_id"]: m for m in json.load(open(SW / "manifest.json"))}
ids = [c for c in man if c in M and "voice" in R[c]]
rng = np.random.default_rng(0)

print("tag counts:", Counter(x for v in T.values() for x in v))
tag_lines = {man[c]["guid"] for c in T if c in man}
era = [c for c in ids if man[c]["guid"] in tag_lines]
FE = ["wavlm_ref", "wavlm_cent", "ecapa_ref", "ecapa_cent", "utmos", "arousal", "dominance",
      "valence", "chars_per_sec", "rms", "peak", "dur", "trail"]


def auc_report(cs, tag, label):
    yy = np.array([tag in T.get(c, []) for c in cs])
    if yy.sum() < 3 or yy.sum() > len(yy) - 3:
        return f"  {label}: n={len(cs)}, positives={int(yy.sum())} (too few)"
    res = []
    for f in FE:
        a = roc_auc_score(yy, [M[c][f] for c in cs])
        res.append((abs(a - 0.5), f, a))
    top = sorted(res, reverse=True)[:3]
    return f"  {label}: n={len(cs)}, pos={int(yy.sum())}: " + ", ".join(f"{f} {a:.2f}" for _, f, a in top)


print("\n=== tag AUROC pooled and within each cfg (removes the 'detects low cfg' confound) ===")
for tag in ["gravelly", "whisper", "rhotic", "rushed", "high", "other"]:
    print(tag)
    print(auc_report(era, tag, "all cfg"))
    for cfg in (1.5, 2.0, 2.5, 3.0):
        print(auc_report([c for c in era if man[c]["cfg_value"] == cfg], tag, f"cfg {cfg}"))

print("\n=== positives per cfg (tag-era lines) ===")
for tag in ["gravelly", "whisper", "rhotic", "rushed", "high"]:
    print(tag, {cfg: sum(tag in T.get(c, []) for c in era if man[c]["cfg_value"] == cfg) for cfg in (1.5, 2.0, 2.5, 3.0)})

# ---- leave-one-line-out regret ----
print("\n=== leave-one-line-out selection quality (voice rating, 1-5) ===")
lines = defaultdict(list)
for c in ids:
    lines[man[c]["guid"]].append(c)


def lolo_scores(feats, sign=None):
    sign = sign or {}
    out = {}
    for g, cs in lines.items():
        others = [c for c in ids if man[c]["guid"] != g]
        s = np.zeros(len(cs))
        for f in feats:
            x = np.array([M[c][f] for c in others])
            s += sign.get(f, 1) * (np.array([M[c][f] for c in cs]) - x.mean()) / x.std()
        out[g] = s
    return out


def regret(score_by_line):
    reg_mean, reg_max, near = [], [], []
    for g, cs in lines.items():
        h = np.array([R[c]["voice"] for c in cs], float)
        pick = h[np.argmax(score_by_line[g])]
        reg_mean.append(pick - h.mean())
        reg_max.append(h.max() - pick)
        near.append(pick >= h.max() - 1)
    return np.mean(reg_mean), np.mean(reg_max), np.mean(near)


rand_gain = np.mean([np.mean([R[c]["voice"] for c in cs]) for cs in lines.values()])
rand_max = np.mean([max(R[c]["voice"] for c in cs) - np.mean([R[c]["voice"] for c in cs]) for cs in lines.values()])
print(f"random pick: gain over line mean = 0.00 ; oracle gain = +{rand_max:.2f} ; line mean voice = {rand_gain:.2f}")
for name, fs in {"ecapa_ref": ["ecapa_ref"], "wavlm_ref": ["wavlm_ref"], "utmos": ["utmos"],
                 "ecapa+wavlm (refs)": ["ecapa_ref", "wavlm_ref"],
                 "ecapa+wavlm+utmos": ["ecapa_ref", "wavlm_ref", "utmos"],
                 "all 5 (pre-specified)": ["ecapa_ref", "wavlm_ref", "wavlm_cent", "ecapa_cent", "utmos"]}.items():
    g_mean, g_max, near = regret(lolo_scores(fs))
    print(f"{name:24s} gain over mean {g_mean:+.2f} | regret vs best {g_max:.2f} | pick within 1 of best {near:.0%}")
# bootstrap over lines for the 5-metric combo
sc = lolo_scores(["ecapa_ref", "wavlm_ref", "wavlm_cent", "ecapa_cent", "utmos"])
gains = []
for g, cs in lines.items():
    h = np.array([R[c]["voice"] for c in cs], float)
    gains.append(h[np.argmax(sc[g])] - h.mean())
bs = [np.mean(rng.choice(gains, len(gains))) for _ in range(2000)]
print(f"5-metric gain over line mean: {np.mean(gains):+.2f}  95% CI [{np.percentile(bs, 2.5):+.2f}, {np.percentile(bs, 97.5):+.2f}] over {len(gains)} lines")

# ---- audEERING cluster test on real, ear-labelled clips ----
print("\n=== audEERING recognition test on real Abelard clips (ear-verified labels) ===")
import torch
from probe_metrics import DEV, EmotionModel, load16k
from transformers import Wav2Vec2Processor

cur = json.load(open(ROOT / "data/voices/emotion_banks/curation.json"))["Abelard"]
name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
proc = Wav2Vec2Processor.from_pretrained(name)
emo = EmotionModel.from_pretrained(name).eval().to(DEV)
X, Y, EV = [], [], []
for ev, rec in cur.items():
    p = ROOT / "data/voices/wav/Abelard" / f"{ev}.wav"
    if not rec.get("emotion") or not p.exists() or rec.get("decision") == "reject":
        continue
    w = load16k(p)
    y = proc(w.numpy(), sampling_rate=16000)["input_values"][0].reshape(1, -1)
    with torch.no_grad():
        _, lg = emo(torch.from_numpy(y).to(DEV))
    X.append(lg.cpu().numpy()[0]); Y.append(rec["emotion"]); EV.append(ev)
X = np.array(X)  # arousal, dominance, valence
cnt = Counter(Y)
print(f"{len(Y)} labelled non-rejected clips, {len(cnt)} labels; top: {cnt.most_common(8)}")
keep = [i for i, y in enumerate(Y) if cnt[y] >= 4]
Xk, Yk = X[keep], np.array(Y)[keep]
labs = sorted(set(Yk))
print(f"labels with >=4 clips: {len(labs)} ({len(Yk)} clips)")
mu, sd = Xk.mean(0), Xk.std(0)
Z = (Xk - mu) / sd


def loo_acc(Z, Yv):
    ok = 0
    for i in range(len(Z)):
        m = np.ones(len(Z), bool); m[i] = False
        cents = {l: Z[m & (Yv == l)].mean(0) for l in set(Yv[m])}
        ok += min(cents, key=lambda l: np.linalg.norm(Z[i] - cents[l])) == Yv[i]
    return ok / len(Z)


acc = loo_acc(Z, Yk)
perm = [loo_acc(Z, rng.permutation(Yk)) for _ in range(200)]
maj = Counter(Yk).most_common(1)[0][1] / len(Yk)
print(f"leave-one-out nearest-centroid accuracy {acc:.2f} | majority-class {maj:.2f} | shuffled-label mean {np.mean(perm):.2f} (95th pct {np.percentile(perm, 95):.2f})")
print(f"silhouette (true labels) {silhouette_score(Z, Yk):+.2f}")
for k, dim in enumerate(["arousal", "dominance", "valence"]):
    groups = [Xk[Yk == l, k] for l in labs]
    F, p = f_oneway(*groups)
    print(f"  {dim}: ANOVA across labels F={F:.2f} p={p:.3g}")
print("mean A/D/V per label (arousal, dominance, valence):")
for l in sorted(labs, key=lambda l: -cnt[l]):
    print(f"  {l:14s} n={cnt[l]:2d}  " + " ".join(f"{v:.2f}" for v in Xk[Yk == l].mean(0)))
