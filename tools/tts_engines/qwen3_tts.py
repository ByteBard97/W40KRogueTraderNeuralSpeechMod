"""Qwen3-TTS Base adapter (Apache 2.0). Voice cloning from a (audio, transcript) reference."""
import re
import numpy as np

MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

_QUOTED = re.compile(r'"([^"]*)"')


def _spoken_only(ref_text):
    # Reference transcripts in this project's catalog are full game-script lines: narration
    # description (never vocalized in the audio) interleaved with quoted dialogue (what's
    # actually spoken in the clip). Qwen3-TTS-Base's ICL voice-clone prompt does strict
    # text/audio alignment, so handing it the narration text alongside a clip that only
    # contains the quoted speech breaks its stop-token prediction - reproduced on the
    # PRL_TheodorasFate_02 "fear" reference: full text -> generation never stops (runs to
    # max_new_tokens every time, any cap); quoted-dialogue-only text -> stops cleanly at a
    # few seconds, consistently across repeated trials. Other engines tolerate the full text
    # fine (no strict ICL alignment), so this trim is scoped to this adapter only.
    quotes = _QUOTED.findall(ref_text)
    return " ".join(q.strip() for q in quotes if q.strip()) or ref_text


def load():
    import torch
    from qwen_tts import Qwen3TTSModel
    device = "cuda:0" if torch.cuda.is_available() else "mps"  # Mac mini renders on MPS
    model = Qwen3TTSModel.from_pretrained(MODEL, device_map=device, dtype=torch.bfloat16)
    return {"model": model, "clone_cache": {}}


def synth(ctx, text, prompt_wav=None, prompt_text=None, **_unused):
    # _unused: e.g. `instruct` from annotation_bridge.for_instruct_engine - the Base model's
    # generate_voice_clone doesn't take a style prompt; a future VoiceDesign-backed engine would.
    model = ctx["model"]
    # The library's own default (max_new_tokens=2048, uncapped by us) lets a failed-to-stop
    # generation run to ~655s of audio regardless of how short the input text is - observed on
    # 5/19 lines in one Abelard bake-off batch, each independently running to that exact same
    # ceiling (a classic autoregressive missing-EOS runaway, not garbage proportional to input).
    # Calibration: at max_new_tokens=2048 the runaway output measured 655.28s, i.e. ~3.13
    # tokens/sec of audio. Bounding max_new_tokens to comfortably more than any real line should
    # need (per-char rate for legitimate output here tops out around 0.1-0.2s/char, so 1.5
    # tokens/char is generous headroom) turns an 11-minute unusable clip into a much shorter,
    # still-obviously-wrong one instead - bounded by the library's own 2048 ceiling for
    # unusually long lines.
    max_new_tokens = min(2048, max(100, round(len(text) * 1.5)))
    if prompt_wav:
        prompt = ctx["clone_cache"].get(prompt_wav)
        if prompt is None:
            prompt = model.create_voice_clone_prompt(
                ref_audio=prompt_wav, ref_text=_spoken_only(prompt_text)
            )
            ctx["clone_cache"][prompt_wav] = prompt
        wavs, sr = model.generate_voice_clone(text=text, voice_clone_prompt=prompt, max_new_tokens=max_new_tokens)
    else:
        wavs, sr = model.generate_voice_clone(text=text, max_new_tokens=max_new_tokens)
    wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
    return np.asarray(wav, dtype=np.float32).reshape(-1), sr
