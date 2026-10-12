"""English accent probabilities with the CommonAccent XLSR classifier (speechbrain).

Run in the scorer venv (tools/scorer/.venv-scorer). The fine-grained top label is noisy (real British
game VO came back as wales/newzealand/australia), so the useful number is p_us: how American a clip
sounds. Gate on p_us against a threshold calibrated from the real game clips (see calibrate.py).
"""
from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "data/voice_design/_accent_model"
SOURCE = "Jzuluaga/accent-id-commonaccent_xlsr-en-english"


class AccentScorer:
    def __init__(self, device: str = "cpu"):
        from speechbrain.inference.interfaces import foreign_class
        self.clf = foreign_class(source=SOURCE, pymodule_file="custom_interface.py",
                                 classname="CustomEncoderWav2vec2Classifier",
                                 savedir=str(MODEL_DIR), run_opts={"device": device})
        ind = self.clf.hparams.label_encoder.lab2ind
        self.labels = [k for k, _ in sorted(ind.items(), key=lambda kv: kv[1])]

    def probs(self, wav_path: str) -> dict[str, float]:
        out_prob, _score, _idx, _lab = self.clf.classify_file(wav_path)
        v = out_prob.squeeze().tolist()
        if any(x < 0 for x in v):  # log-probabilities -> probabilities
            v = [math.exp(x) for x in v]
        s = sum(v) or 1.0
        return {lab: round(x / s, 4) for lab, x in zip(self.labels, v)}

    def summary(self, wav_path: str) -> dict:
        p = self.probs(wav_path)
        top = max(p, key=p.get)
        return {"p_us": p["us"], "top": top, "p_top": p[top], "p_uk": round(p["england"] + p["scotland"] + p["wales"] + p["ireland"], 4)}
