"""Original Chatterbox adapter (Resemble AI, MIT). 500M, working exaggeration/cfg_weight -
unlike Turbo, these are real generation-time controls (see docs/superpowers/plans/
2026-09-04-emotional-expressiveness-fix.md for why this exists alongside chatterbox_turbo.py)."""
import numpy as np


def load():
    import torch
    from chatterbox.tts import ChatterboxTTS
    model = ChatterboxTTS.from_pretrained(device="cuda" if torch.cuda.is_available() else "cpu")
    return model


def synth(model, text, prompt_wav=None, prompt_text=None, exaggeration=None, cfg_weight=None):
    kwargs = {}
    if prompt_wav:
        kwargs["audio_prompt_path"] = prompt_wav
    if exaggeration is not None:
        kwargs["exaggeration"] = exaggeration
    if cfg_weight is not None:
        kwargs["cfg_weight"] = cfg_weight
    wav = model.generate(text, **kwargs)
    return np.asarray(wav.squeeze().cpu().numpy(), dtype=np.float32), model.sr
