"""THROWAWAY PROBE: can audeering pooled embeddings score emotion?
(a) cosine(gen, emotion-matched reference) vs the user's emotion ratings (228 sweep clips)
(b) leave-one-out logistic-regression probe on the 135 ear-labelled real clips."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from scipy.stats import kendalltau, spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from transformers import Wav2Vec2Processor

sys.path.insert(0, str(Path(__file__).parent))
from probe_metrics import DEV, EmotionModel, load16k

ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / "data/bakeoff_abelard_cfg_sweep"
man = json.load(open(SW / "manifest.json"))
R = json.load(open(SW / "ratings.json"))
name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
proc = Wav2Vec2Processor.from_pretrained(name)
emo = EmotionModel.from_pretrained(name).eval().to(DEV)


def emb(path):
    w = load16k(path)
    y = proc(w.numpy(), sampling_rate=16000)["input_values"][0].reshape(1, -1)
    with torch.no_grad():
        h, _ = emo(torch.from_numpy(y).to(DEV))
    return h.cpu().numpy()[0]


cos = lambda a, b: float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

# (a) reference-relative embedding similarity vs emotion ratings
ref_cache, rows = {}, []
for m in man:
    if "emotion" not in R.get(m["cell_id"], {}):
        continue
    rp = m["reference"]["wav"]
    ref_cache.setdefault(rp, emb(rp))
    rows.append((m["guid"], cos(emb(ROOT / m["wav_path"]), ref_cache[rp]), R[m["cell_id"]]["emotion"], R[m["cell_id"]].get("voice")))
s = np.array([r[1] for r in rows]); e = np.array([r[2] for r in rows], float); v = np.array([r[3] for r in rows], float)
print(f"(a) audeering-embedding cosine to reference: rho vs emotion {spearmanr(s, e)[0]:+.2f}, vs voice {spearmanr(s, v)[0]:+.2f} (n={len(rows)})")
by = defaultdict(list)
for g, x, y, _ in rows:
    by[g].append((x, y))
taus = [kendalltau(*zip(*ps))[0] for ps in by.values() if np.ptp([p[1] for p in ps]) > 0]
print(f"    per-line tau vs emotion {np.nanmean(taus):+.2f} over {len(taus)} lines")

# (b) supervised probe on real labelled clips
cur = json.load(open(ROOT / "data/voices/emotion_banks/curation.json"))["Abelard"]
X, Y = [], []
for ev, rec in cur.items():
    p = ROOT / "data/voices/wav/Abelard" / f"{ev}.wav"
    if rec.get("emotion") and p.exists() and rec.get("decision") != "reject":
        X.append(emb(p)); Y.append(rec["emotion"])
X, Y = np.array(X), np.array(Y)
cnt = Counter(Y)
keep = np.array([cnt[y] >= 4 for y in Y])
Xk, Yk = X[keep], Y[keep]
rng = np.random.default_rng(0)


def loo(Xk, Yk):
    ok = 0
    for i in range(len(Xk)):
        m = np.ones(len(Xk), bool); m[i] = False
        sc = StandardScaler().fit(Xk[m])
        clf = LogisticRegression(max_iter=2000, C=0.05).fit(sc.transform(Xk[m]), Yk[m])
        ok += clf.predict(sc.transform(Xk[i:i + 1]))[0] == Yk[i]
    return ok / len(Xk)


acc = loo(Xk, Yk)
perm = [loo(Xk, rng.permutation(Yk)) for _ in range(20)]
print(f"(b) probe on 1024-d audeering embedding, {len(set(Yk))} labels / {len(Yk)} clips: LOO acc {acc:.2f} "
      f"| majority {Counter(Yk).most_common(1)[0][1] / len(Yk):.2f} | shuffled mean {np.mean(perm):.2f} max {np.max(perm):.2f}")

# (c) apply a probe trained on ALL real labelled clips to the generated clips:
#     does P(target emotion) track the user's emotion rating?
cnt2 = Counter(Y)
keep2 = np.array([cnt2[y] >= 2 for y in Y])
X2, Y2 = X[keep2], Y[keep2]
sc = StandardScaler().fit(X2)
clf = LogisticRegression(max_iter=3000, C=0.05).fit(sc.transform(X2), Y2)
cls = list(clf.classes_)
tp, er, gd = [], [], []
for m in man:
    c = m["cell_id"]
    if "emotion" not in R.get(c, {}) or m["emotion"] not in cls:
        continue
    p = clf.predict_proba(sc.transform(emb(ROOT / m["wav_path"]).reshape(1, -1)))[0]
    tp.append(p[cls.index(m["emotion"])]); er.append(R[c]["emotion"]); gd.append(m["guid"])
tp, er = np.array(tp), np.array(er, float)
gb = defaultdict(list)
for g, x, y in zip(gd, tp, er):
    gb[g].append((x, y))
taus = [kendalltau(*zip(*ps))[0] for ps in gb.values() if np.ptp([p[1] for p in ps]) > 0 and np.ptp([p[0] for p in ps]) > 0]
print(f"(c) P(target emotion) from probe vs emotion rating: rho {spearmanr(tp, er)[0]:+.2f} (n={len(tp)}, {len(set(gd))} lines with a target label the probe knows), per-line tau {np.nanmean(taus):+.2f}")
