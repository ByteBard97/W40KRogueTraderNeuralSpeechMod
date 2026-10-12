"""ECAPA consistency + accent check on narrator candidate clips (run in tools/scorer/.venv-scorer)."""
import json, os, sys
import numpy as np, torch, torchaudio, soundfile as sf
sys.path.insert(0, "tools/voice_design")
from accent import AccentScorer
from speechbrain.inference.speaker import EncoderClassifier

cand = json.load(open(os.path.expanduser("~/bg3-work/cand.json")))
enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                     savedir="data/scorer_probe/ecapa_model", run_opts={"device": "cpu"})
embs = []
for r in cand:
    x, sr = sf.read(r["wav"], dtype="float32"); x = x.mean(1) if x.ndim > 1 else x; w = torchaudio.functional.resample(torch.from_numpy(x)[None], sr, 16000)
    embs.append(torch.nn.functional.normalize(enc.encode_batch(w).squeeze(), dim=-1))
E = torch.stack(embs); c = torch.nn.functional.normalize(E.mean(0), dim=-1)
sims = (E @ c).numpy()
print("centroid cos: min %.2f p10 %.2f median %.2f" % (sims.min(), np.percentile(sims, 10), np.median(sims)))
acc = AccentScorer()
for r, s in zip(cand, sims):
    r["ecapa_cent"] = float(s)
top = sorted(cand, key=lambda r: -r["score"])[:40]
for r in top:
    r["p_us"] = acc.summary(r["wav"]).get("p_us")
json.dump(cand, open(os.path.expanduser("~/bg3-work/cand_scored.json"), "w"), indent=1)
print("outliers (<0.5):", sum(1 for s in sims if s < 0.5))
print("p_us of top-40:", sorted(round(r["p_us"], 2) for r in top if r["p_us"] is not None))
