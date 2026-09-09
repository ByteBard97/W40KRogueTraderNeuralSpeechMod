"""Chatterbox-Turbo adapter (Resemble AI, MIT). 350M, tag-aware ([laugh], [sigh], ...)."""
import numpy as np


def load():
    import torch
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    model = ChatterboxTurboTTS.from_pretrained(device="cuda" if torch.cuda.is_available() else "cpu")
    return model


def synth(model, text, prompt_wav=None, prompt_text=None, exaggeration=None, cfg_weight=None):
    kwargs = {}
    if prompt_wav:
        kwargs["audio_prompt_path"] = prompt_wav
    if exaggeration is not None:
        kwargs["exaggeration"] = exaggeration
    # cfg_weight intentionally not forwarded: Turbo ignores it and logs a warning if passed.
    wav = model.generate(text, **kwargs)
    return np.asarray(wav.squeeze().cpu().numpy(), dtype=np.float32), model.sr
