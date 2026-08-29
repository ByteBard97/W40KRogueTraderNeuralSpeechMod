"""IndexTTS-2.5 adapter (IndexTeam, weights non-commercial). Zero-shot cloning; best published
speaker-similarity numbers of the shortlist; emotion via a separate reference clip or vector
(not exercised here - plain cloning only, matching the other engines' bake-off round 1)."""
import os
import sys
from pathlib import Path

import numpy as np

INDEXTTS_DIR = Path(__file__).resolve().parent.parent.parent / "reference/index-tts"


def load():
    sys.path.insert(0, str(INDEXTTS_DIR))
    os.chdir(INDEXTTS_DIR)  # the package resolves checkpoints/... relative to cwd
    from indextts.infer_v2_5 import IndexTTS2
    return IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_bf16=True)


def synth(model, text, prompt_wav=None, prompt_text=None):
    if not prompt_wav:
        raise ValueError("IndexTTS-2.5 requires a speaker reference clip (no built-in default voice)")
    sr, wav_int16 = model.infer(spk_audio_prompt=prompt_wav, text=text, output_path=None, lang="en", verbose=False)
    audio = np.asarray(wav_int16, dtype=np.float32).reshape(-1) / 32768.0
    return audio, sr
