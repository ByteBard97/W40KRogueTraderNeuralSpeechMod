"""Qwen3-TTS Base adapter (Apache 2.0). Voice cloning from a (audio, transcript) reference."""
import numpy as np

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def load():
    import torch
    from qwen_tts import Qwen3TTSModel
    model = Qwen3TTSModel.from_pretrained(MODEL, device_map="cuda:0", dtype=torch.bfloat16)
    return {"model": model, "clone_cache": {}}


def synth(ctx, text, prompt_wav=None, prompt_text=None, **_unused):
    # _unused: e.g. `instruct` from annotation_bridge.for_instruct_engine - the Base model's
    # generate_voice_clone doesn't take a style prompt; a future VoiceDesign-backed engine would.
    model = ctx["model"]
    if prompt_wav:
        prompt = ctx["clone_cache"].get(prompt_wav)
        if prompt is None:
            prompt = model.create_voice_clone_prompt(ref_audio=prompt_wav, ref_text=prompt_text)
            ctx["clone_cache"][prompt_wav] = prompt
        wavs, sr = model.generate_voice_clone(text=text, voice_clone_prompt=prompt)
    else:
        wavs, sr = model.generate_voice_clone(text=text)
    wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
    return np.asarray(wav, dtype=np.float32).reshape(-1), sr
