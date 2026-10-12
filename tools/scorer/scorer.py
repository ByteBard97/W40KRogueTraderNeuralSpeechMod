"""Automatic scoring of cloned TTS clips: voice match, artifacts, and emotion family.

Runs in tools/scorer/.venv-scorer (separate from the TTS engine envs). Evidence for the
metric choices is in docs/research/ and the probe results (tools/scorer/probe_*.py):
speaker embeddings + UTMOSv2 rank takes of one line usefully; emotion is scored by a probe
trained on the character's own ear-verified clips, not by raw distances.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("HF_HOME", "/media/geoff/Elements/hf_cache_scorer")

import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torchaudio
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2Processor, WavLMForXVector
from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/audio_emotion_labeling"))
from families import FAMILY_OF  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from selection import VOICE_FEATURES, voice_composite  # noqa: E402,F401

SR = 16000
EMO_MODEL = "audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim"


def load16k(path) -> torch.Tensor:
    wav, sr = sf.read(str(path), dtype="float32", always_2d=True)
    wav = torch.from_numpy(wav.mean(1))
    return torchaudio.functional.resample(wav, sr, SR) if sr != SR else wav


class _RegressionHead(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, x):
        return self.out_proj(self.dropout(torch.tanh(self.dense(self.dropout(x)))))


class _EmotionModel(Wav2Vec2PreTrainedModel):
    """audEERING dimensional model (per its model card); post_init() for transformers 5."""

    def __init__(self, config):
        super().__init__(config)
        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = _RegressionHead(config)
        self.post_init()

    def forward(self, input_values):
        hidden = self.wav2vec2(input_values)[0].mean(dim=1)
        return hidden, self.classifier(hidden)


@dataclass
class ClipEmbeddings:
    wavlm: torch.Tensor
    ecapa: torch.Tensor
    emo: np.ndarray  # audEERING pooled hidden state, 1024-d


class ClipScorer:
    """Loads all models once. Not thread-safe."""

    def __init__(self, device: str = "cuda", with_asr: bool = True, asr_device: str | None = None):
        from speechbrain.inference.speaker import EncoderClassifier

        self.dev = device
        self.fe = Wav2Vec2FeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
        self.wavlm = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").eval().to(device)
        self.ecapa = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(ROOT / "data/scorer_probe/ecapa_model"), run_opts={"device": device})
        self.emo_proc = Wav2Vec2Processor.from_pretrained(EMO_MODEL)
        self.emo = _EmotionModel.from_pretrained(EMO_MODEL).eval().to(device)
        import utmosv2
        self.mos = utmosv2.create_model(pretrained=True)
        self.asr = None
        if with_asr:
            from faster_whisper import WhisperModel
            asr_device = asr_device or device
            self.asr = WhisperModel("large-v3", device=asr_device,
                                    compute_type="float16" if asr_device == "cuda" else "int8")

    def embed(self, wav: torch.Tensor) -> ClipEmbeddings:
        x = self.fe([wav.numpy()], sampling_rate=SR, return_tensors="pt", padding=True).to(self.dev)
        with torch.no_grad():
            w = torch.nn.functional.normalize(self.wavlm(**x).embeddings, dim=-1).cpu()[0]
            e = torch.nn.functional.normalize(self.ecapa.encode_batch(wav.unsqueeze(0).to(self.dev)).squeeze(), dim=-1).cpu()
            y = self.emo_proc(wav.numpy(), sampling_rate=SR)["input_values"][0].reshape(1, -1)
            h, _ = self.emo(torch.from_numpy(y).to(self.dev))
        return ClipEmbeddings(w, e, h.cpu().numpy()[0])

    def utmos(self, path) -> float:
        return float(self.mos.predict(input_path=str(path)))

    def transcribe(self, wav: torch.Tensor) -> str:
        segs, _ = self.asr.transcribe(wav.numpy(), language="en", vad_filter=True)
        return " ".join(s.text for s in segs)


class Character:
    """Per-character calibration built from that character's real, labelled clips."""

    def __init__(self, scorer: ClipScorer, wav_dir: Path, curation: dict, families=FAMILY_OF):
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        self.scorer = scorer
        embs, X, Y = [], [], []
        for p in sorted(wav_dir.glob("*.wav")):
            try:
                e = scorer.embed(load16k(p))
            except Exception as err:  # a few game clips are unusable; skip rather than abort
                print(f"skip {p.name}: {err}")
                continue
            if not (torch.isfinite(e.wavlm).all() and torch.isfinite(e.ecapa).all()):
                print(f"skip non-finite embedding: {p.name}")
                continue
            embs.append(e)
            rec = curation.get(p.stem, {})
            if rec.get("emotion") in families:
                X.append(e.emo)
                Y.append(families[rec["emotion"]])
        self.cent_wavlm = torch.stack([e.wavlm for e in embs]).mean(0)
        self.cent_ecapa = torch.stack([e.ecapa for e in embs]).mean(0)
        self.families = families
        self.scaler = StandardScaler().fit(np.array(X))
        self.probe = LogisticRegression(max_iter=3000, C=0.05, class_weight="balanced").fit(
            self.scaler.transform(np.array(X)), np.array(Y))
        self.label_counts = Counter(Y)

    def family_probs(self, emo_emb: np.ndarray) -> dict[str, float]:
        p = self.probe.predict_proba(self.scaler.transform(emo_emb.reshape(1, -1)))[0]
        return dict(zip(self.probe.classes_, map(float, p)))

    def score(self, gen_path, ref_path, text: str | None = None, target_label: str | None = None) -> dict:
        s = self.scorer
        gen, ref = load16k(gen_path), load16k(ref_path)
        g, r = s.embed(gen), s.embed(ref)
        cos = lambda a, b: float(torch.nn.functional.cosine_similarity(a, b, dim=-1))
        a = gen.numpy()
        env = np.abs(a)
        active = np.where(env > 0.02 * env.max())[0]
        out = {
            "wavlm_ref": cos(g.wavlm, r.wavlm), "ecapa_ref": cos(g.ecapa, r.ecapa),
            "wavlm_cent": cos(g.wavlm, self.cent_wavlm), "ecapa_cent": cos(g.ecapa, self.cent_ecapa),
            "utmos": s.utmos(gen_path), "dur": len(a) / SR,
            "trail_silence": float((len(a) - active[-1]) / SR) if len(active) else 0.0,
            "clipped": bool(env.max() >= 0.999),
        }
        probs = self.family_probs(g.emo)
        out["family_probs"] = probs
        fam = self.families.get(target_label) if target_label else None
        out["target_family"] = fam
        out["p_target_family"] = probs.get(fam) if fam else None
        if text and s.asr is not None:
            import re
            import jiwer
            norm = lambda t: " ".join(re.findall(r"[a-z']+", t.lower().replace("—", " ").replace("-", " ")))
            hyp = s.transcribe(gen)
            out["hyp"] = hyp
            out["wer"] = float(jiwer.wer(norm(text), norm(hyp))) if norm(hyp) else 1.0
        return out
