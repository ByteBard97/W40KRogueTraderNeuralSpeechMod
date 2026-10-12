"""THROWAWAY PROBE: score the 228 cfg-sweep clips with candidate automatic metrics.

Question: do free local metrics track the user's hand ratings? Output is
data/scorer_probe/metrics.json, analysed by probe_analyze.py. Not production code.
"""
import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("HF_HOME", "/media/geoff/Elements/hf_cache_scorer")

import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torchaudio
from transformers import (
    Wav2Vec2FeatureExtractor,
    Wav2Vec2Processor,
    WavLMForXVector,
)
from transformers.models.wav2vec2.modeling_wav2vec2 import (
    Wav2Vec2Model,
    Wav2Vec2PreTrainedModel,
)

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / "data/bakeoff_abelard_cfg_sweep"
OUT = ROOT / "data/scorer_probe"
OUT.mkdir(parents=True, exist_ok=True)
DEV = "cuda"
SR = 16000


def load16k(path):
    wav, sr = sf.read(str(path), dtype="float32", always_2d=True)
    wav = torch.from_numpy(wav.mean(1))
    if sr != SR:
        wav = torchaudio.functional.resample(wav, sr, SR)
    return wav


class RegressionHead(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = self.dropout(features)
        x = torch.tanh(self.dense(x))
        return self.out_proj(self.dropout(x))


class EmotionModel(Wav2Vec2PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = RegressionHead(config)
        self.post_init()

    def forward(self, input_values):
        hidden = self.wav2vec2(input_values)[0].mean(dim=1)
        return hidden, self.classifier(hidden)


def cos(a, b):
    return float(torch.nn.functional.cosine_similarity(a, b, dim=-1))


def main():
    manifest = json.load(open(SWEEP / "manifest.json"))

    fe = Wav2Vec2FeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
    wavlm = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").eval().to(DEV)

    def wavlm_emb(w):
        x = fe([w.numpy()], sampling_rate=SR, return_tensors="pt", padding=True).to(DEV)
        with torch.no_grad():
            e = wavlm(**x).embeddings
        return torch.nn.functional.normalize(e, dim=-1).cpu()[0]

    from speechbrain.inference.speaker import EncoderClassifier
    ecapa = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(OUT / "ecapa_model"), run_opts={"device": DEV})

    def ecapa_emb(w):
        with torch.no_grad():
            e = ecapa.encode_batch(w.unsqueeze(0).to(DEV)).squeeze()
        return torch.nn.functional.normalize(e, dim=-1).cpu()

    name = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"
    proc = Wav2Vec2Processor.from_pretrained(name)
    emo = EmotionModel.from_pretrained(name).eval().to(DEV)

    def avd(w):
        y = proc(w.numpy(), sampling_rate=SR)["input_values"][0].reshape(1, -1)
        with torch.no_grad():
            _, logits = emo(torch.from_numpy(y).to(DEV))
        return logits.cpu().numpy()[0].tolist()  # arousal, dominance, valence

    from faster_whisper import WhisperModel
    import jiwer
    asr = WhisperModel("large-v3", device=DEV, compute_type="float16")

    def norm_words(s):
        return re.findall(r"[a-z']+", s.lower().replace("—", " ").replace("-", " "))

    def mask_names(text):
        # heuristic: capitalised word not at a sentence start = proper noun -> dropped
        toks = re.findall(r"[A-Za-z']+|[.!?]", text)
        out, start = [], True
        for t in toks:
            if t in ".!?":
                start = True
                continue
            if not (t[0].isupper() and not start):
                out.append(t.lower())
            start = False
        return out

    import utmosv2
    mos_model = utmosv2.create_model(pretrained=True)

    # character centroid of real Abelard clips (channel-neutral identity anchor)
    real = sorted((ROOT / "data/voices/wav/Abelard").glob("*.wav"))
    def centroid(fn):
        embs = []
        for p in real:
            e = fn(load16k(p))
            if torch.isfinite(e).all():
                embs.append(e)
            else:
                print("non-finite embedding, skipped:", p.name, flush=True)
        return torch.stack(embs).mean(0)

    cent_w = centroid(wavlm_emb)
    cent_e = centroid(ecapa_emb)
    print(f"centroid from {len(real)} real clips", flush=True)

    ref_cache = {}
    results = {}
    for i, m in enumerate(manifest):
        cid = m["cell_id"]
        gen = load16k(ROOT / m["wav_path"])
        refp = Path(m["reference"]["wav"])
        if refp not in ref_cache:
            rw = load16k(refp)
            ref_cache[refp] = (wavlm_emb(rw), ecapa_emb(rw), avd(rw))
        rw_e, re_e, r_avd = ref_cache[refp]
        gw, ge = wavlm_emb(gen), ecapa_emb(gen)
        segs, _ = asr.transcribe(gen.numpy(), language="en", vad_filter=True)
        hyp = " ".join(s.text for s in segs)
        ref_words = norm_words(m["text"])
        ref_masked = mask_names(m["text"])
        hyp_words = norm_words(hyp)
        wer = jiwer.wer(" ".join(ref_words), " ".join(hyp_words)) if hyp_words else 1.0
        from collections import Counter
        miss = Counter(ref_masked) - Counter(hyp_words)
        wer_common = sum(miss.values()) / max(len(ref_masked), 1)  # names excluded; recall-style
        a = gen.numpy()
        env = np.abs(a)
        active = np.where(env > 0.02 * env.max())[0]
        lead = active[0] / SR if len(active) else 0.0
        trail = (len(a) - active[-1]) / SR if len(active) else 0.0
        dur = len(a) / SR
        g_avd = avd(gen)
        results[cid] = {
            "wavlm_ref": cos(gw, rw_e), "wavlm_cent": cos(gw, cent_w),
            "ecapa_ref": cos(ge, re_e), "ecapa_cent": cos(ge, cent_e),
            "arousal": g_avd[0], "dominance": g_avd[1], "valence": g_avd[2],
            "ref_arousal": r_avd[0], "ref_dominance": r_avd[1], "ref_valence": r_avd[2],
            "wer": wer, "wer_masked": wer_common, "hyp": hyp,
            "dur": dur, "chars_per_sec": len(m["text"]) / dur, "lead": float(lead), "trail": float(trail),
            "peak": float(env.max()), "rms": float(np.sqrt((a ** 2).mean())),
            "utmos": float(mos_model.predict(input_path=str(ROOT / m["wav_path"]))),
        }
        if i % 20 == 0:
            print(i, cid, {k: round(v, 3) for k, v in results[cid].items() if isinstance(v, float)}, flush=True)
            json.dump(results, open(OUT / "metrics.json", "w"))
    json.dump(results, open(OUT / "metrics.json", "w"), indent=1)
    print("done", len(results))


if __name__ == "__main__":
    sys.exit(main())
