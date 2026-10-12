"""THROWAWAY PROBE: family-level LOO probe on audeering embeddings (same 136 clips/8 families as the audio-LLM pilot)."""
import json, sys
from collections import Counter
from pathlib import Path
import numpy as np, torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import recall_score
from transformers import Wav2Vec2Processor
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, str(Path(__file__).parents[1] / "audio_emotion_labeling"))
from probe_metrics import DEV, EmotionModel, load16k
from families import FAMILY_OF
ROOT = Path(__file__).resolve().parents[2]
name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
proc = Wav2Vec2Processor.from_pretrained(name); emo = EmotionModel.from_pretrained(name).eval().to(DEV)
def emb(p):
    y = proc(load16k(p).numpy(), sampling_rate=16000)["input_values"][0].reshape(1, -1)
    with torch.no_grad(): return emo(torch.from_numpy(y).to(DEV))[0].cpu().numpy()[0]
cur = json.load(open(ROOT / "data/voices/emotion_banks/curation.json"))["Abelard"]
X, Y = [], []
for ev, rec in cur.items():
    p = ROOT / "data/voices/wav/Abelard" / f"{ev}.wav"
    if rec.get("emotion") and p.exists() and rec["emotion"] in FAMILY_OF:
        X.append(emb(p)); Y.append(FAMILY_OF[rec["emotion"]])
X, Y = np.array(X), np.array(Y); print(len(Y), Counter(Y))
rng = np.random.default_rng(0)
def loo(X, Y, bal=None):
    pr = []
    for i in range(len(X)):
        m = np.ones(len(X), bool); m[i] = False
        sc = StandardScaler().fit(X[m]); clf = LogisticRegression(max_iter=3000, C=0.05, class_weight=bal).fit(sc.transform(X[m]), Y[m])
        pr.append(clf.predict(sc.transform(X[i:i+1]))[0])
    return np.array(pr)
for bal in (None, "balanced"):
    pr = loo(X, Y, bal); print(f"class_weight={bal}: LOO top-1 {(pr==Y).mean():.3f} (majority {Counter(Y).most_common(1)[0][1]/len(Y):.3f}); "
        f"macro-recall {recall_score(Y, pr, average='macro', zero_division=0):.3f}")
    print("  recall per family:", {f: round(float((pr[Y==f]==f).mean()),2) for f in sorted(set(Y))})
perm = [(loo(X, rng.permutation(Y), "balanced") == Y).mean() for _ in range(5)]
print("shuffled-label top-1 (balanced):", np.round(perm, 3))
