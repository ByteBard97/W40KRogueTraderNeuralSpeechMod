"""THROWAWAY PROBE: UniSpeech WavLM-large+ECAPA-TDNN SV (seed-tts-eval SIM-o) vs the metrics in
data/scorer_probe/metrics.json, against the user's voice ratings on the cfg sweep.

Weights: HF mirror bezzam/wavlm_large_finetune_seed_tts_eval (CC BY-SA 3.0), cached under HF_HOME.
Embeddings cache: data/scorer_probe/wavlm_large_emb.json. Runs on CPU unless --gpu.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("HF_HOME", "/media/geoff/Elements/hf_cache_scorer")
import numpy as np
import soundfile as sf
import torch
import torchaudio
from scipy.stats import kendalltau, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from vendor.unispeech.sv_model import embed, load_sv  # noqa: E402

SW = ROOT / "data/bakeoff_abelard_cfg_sweep"
CACHE = ROOT / "data/scorer_probe/wavlm_large_emb.json"
SR = 16000


def load16k(p):
    w, sr = sf.read(str(p), dtype="float32", always_2d=True)
    w = torch.from_numpy(w.mean(1))
    return torchaudio.functional.resample(w, sr, SR) if sr != SR else w


def compute_embeddings(dev):
    from huggingface_hub import hf_hub_download
    ck = hf_hub_download("bezzam/wavlm_large_finetune_seed_tts_eval", "wavlm_large_finetune.pth")
    model = load_sv(ck, dev)
    man = json.load(open(SW / "manifest.json"))
    paths = {"gen:" + m["cell_id"]: ROOT / m["wav_path"] for m in man}
    for m in man:
        paths["ref:" + m["reference"]["wav"]] = Path(m["reference"]["wav"])
    for p in sorted((ROOT / "data/voices/wav/Abelard").glob("*.wav")):
        paths["real:" + p.name] = p
    out = {}
    for i, (k, p) in enumerate(paths.items()):
        e = embed(model, load16k(p), dev)
        if torch.isfinite(e).all():
            out[k] = e.tolist()
        else:
            print("non-finite embedding, skipped:", k, flush=True)
        if i % 50 == 0:
            print(i, len(paths), flush=True)
    json.dump(out, open(CACHE, "w"))
    return out


def boot_ci(x, n=10000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x))).mean(1)
    return np.percentile(m, [2.5, 97.5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--recompute", action="store_true")
    a = ap.parse_args()
    dev = "cuda" if a.gpu else "cpu"
    E = json.load(open(CACHE)) if CACHE.exists() and not a.recompute else compute_embeddings(dev)
    E = {k: torch.tensor(v) for k, v in E.items()}
    M = json.load(open(ROOT / "data/scorer_probe/metrics.json"))
    R = json.load(open(SW / "ratings.json"))
    man = {m["cell_id"]: m for m in json.load(open(SW / "manifest.json"))}
    real = [v for k, v in E.items() if k.startswith("real:")]
    cent = torch.nn.functional.normalize(torch.stack(real).mean(0), dim=0)
    print(f"centroid from {len(real)} real clips")

    F = {}
    for c, m in man.items():
        g, r = E.get("gen:" + c), E.get("ref:" + m["reference"]["wav"])
        if g is None or r is None or c not in M or "voice" not in R.get(c, {}):
            continue
        F[c] = {**{k: M[c][k] for k in ("wavlm_ref", "wavlm_cent", "ecapa_ref", "ecapa_cent", "utmos")},
                "large_ref": float(g @ r), "large_cent": float(g @ cent)}
    ids = list(F)
    y = np.array([R[c]["voice"] for c in ids], float)
    lines = defaultdict(list)
    for c in ids:
        lines[man[c]["guid"]].append(c)
    print(f"{len(ids)} clips, {len(lines)} lines")

    def col(f, cs=None):
        return np.array([F[c][f] for c in (cs or ids)])

    def per_line_tau(score):
        t = []
        for cs in lines.values():
            h = [R[c]["voice"] for c in cs]
            if len(set(h)) > 1:
                t.append(kendalltau(h, [score[c] for c in cs])[0])
        return float(np.mean(t))

    def lolo(scorefn):
        gains = []
        for g, cs in lines.items():
            others = [c for c in ids if man[c]["guid"] != g]
            s = scorefn(cs, others)
            h = np.array([R[c]["voice"] for c in cs], float)
            gains.append(h[int(np.argmax(s))] - h.mean())
        return np.mean(gains), boot_ci(gains)

    def single(f):
        return lambda cs, others: col(f, cs)

    def comp(feats):
        def fn(cs, others):
            s = 0
            for f in feats:
                x = col(f, others)
                s = s + (col(f, cs) - x.mean()) / x.std()
            return s
        return fn

    cfgs = (1.5, 2.0, 2.5, 3.0)
    print("\nuser voice mean by cfg:", [round(float(np.mean([R[c]["voice"] for c in ids if man[c]["cfg_value"] == k])), 2) for k in cfgs])
    hdr = f"{'metric':<14}{'spearman':>9}{'lineTau':>8}  " + " ".join(f"cfg{k:<5}" for k in cfgs) + "   min    max    std   LOLO gain [95% CI]"
    print(hdr)
    for f in ("wavlm_ref", "wavlm_cent", "ecapa_ref", "ecapa_cent", "large_ref", "large_cent"):
        x = col(f)
        sc = dict(zip(ids, x))
        bycfg = [np.mean([F[c][f] for c in ids if man[c]["cfg_value"] == k]) for k in cfgs]
        g, ci = lolo(single(f))
        print(f"{f:<14}{spearmanr(x, y)[0]:9.3f}{per_line_tau(sc):8.3f}  " + " ".join(f"{b:8.4f}" for b in bycfg)
              + f"  {x.min():.3f} {x.max():.3f} {x.std():.4f}  {g:+.3f} [{ci[0]:+.3f},{ci[1]:+.3f}]")

    base5 = ["ecapa_ref", "wavlm_ref", "wavlm_cent", "ecapa_cent", "utmos"]
    variants = {
        "base5 (current)": base5,
        "swap: wavlm->large": ["ecapa_ref", "large_ref", "large_cent", "ecapa_cent", "utmos"],
        "add large (7)": base5 + ["large_ref", "large_cent"],
        "swap large_ref only": ["ecapa_ref", "large_ref", "wavlm_cent", "ecapa_cent", "utmos"],
        "large_ref+large_cent+utmos": ["large_ref", "large_cent", "utmos"],
        "large_ref+large_cent": ["large_ref", "large_cent"],
    }
    print("\ncomposites (sum of z-scores, LOLO-standardised)")
    print(f"{'variant':<28}{'spearman':>9}{'lineTau':>8}   LOLO gain [95% CI]")
    for name, feats in variants.items():
        z = 0
        for f in feats:
            x = col(f)
            z = z + (x - x.mean()) / x.std()
        sc = dict(zip(ids, z))
        g, ci = lolo(comp(feats))
        print(f"{name:<28}{spearmanr(z, y)[0]:9.3f}{per_line_tau(sc):8.3f}   {g:+.3f} [{ci[0]:+.3f},{ci[1]:+.3f}]")
    print("\noracle top-take gain:", round(float(np.mean([max(R[c]['voice'] for c in cs) - np.mean([R[c]['voice'] for c in cs]) for cs in lines.values()])), 3))


if __name__ == "__main__":
    main()
