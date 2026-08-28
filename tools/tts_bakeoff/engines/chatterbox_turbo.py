"""Chatterbox-Turbo adapter (Resemble AI, MIT). 350M, tag-aware ([laugh], [sigh], ...)."""
import numpy as np


def load():
    import torch
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    model = ChatterboxTurboTTS.from_pretrained(device="cuda" if torch.cuda.is_available() else "cpu")
    return model


def synth(model, text, prompt_wav=None, prompt_text=None):
    kwargs = {}
    if prompt_wav:
        kwargs["audio_prompt_path"] = prompt_wav
    wav = model.generate(text, **kwargs)
    return np.asarray(wav.squeeze().cpu().numpy(), dtype=np.float32), model.sr
