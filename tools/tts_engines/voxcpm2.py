"""VoxCPM2 (OpenBMB, Apache-2.0, 2B) adapter. The one surveyed model that officially combines
zero-shot cloning AND a natural-language style/emotion instruction in the same call -
"Controllable Voice Cloning" (see docs/research or memory for how this was found, 2026-09-05).
Apache-2.0 is a genuinely clean license (unlike Higgs/Fish/IndexTTS2's non-commercial terms) -
the first emotion-capable bake-off candidate that isn't licensing-disqualified for the public
mod. Also has a full-pipeline ONNX export (CPU-only so far, no proven DirectML path yet).

Runs under the `roguetts` conda env (torch 2.12.1+cu130, includes sm_120/Blackwell support for
the RTX 5080) rather than one of the project's usual .venv-* dirs - reuse rather than downloading
another multi-GB CUDA torch wheel from scratch.
"""
import numpy as np

MODEL_ID = "openbmb/VoxCPM2"


def load():
    from voxcpm import VoxCPM
    return VoxCPM.from_pretrained(MODEL_ID, load_denoiser=False)


def synth(model, text, prompt_wav=None, prompt_text=None, instruct=None):
    # Style/emotion instruction goes as a "(...)" prefix on the text - VoxCPM2's documented
    # Controllable Voice Cloning syntax.
    if instruct:
        text = f"({instruct}){text}"

    kwargs = {}
    if prompt_wav:
        # reference_wav_path only - NOT paired with prompt_wav_path/prompt_text. Verified by a
        # direct test: passing prompt_wav_path+prompt_text (the "Ultimate Cloning"/continuation
        # mode) returns the reference clip's own audio prepended to the output (a ~4-word line
        # came back as 12s, matching the ~8s reference clip + a gap + the real ~3s generation).
        # reference_wav_path alone - the README's actual "Controllable Voice Cloning" example -
        # returns just the new line, no echo, and is the one documented to combine with a style
        # instruction anyway. prompt_text is unused in this mode (kept in the signature for
        # interface parity with the other adapters, which all take it).
        kwargs["reference_wav_path"] = prompt_wav

    wav = model.generate(text=text, cfg_value=2.0, inference_timesteps=10, **kwargs)
    return np.asarray(wav, dtype=np.float32).reshape(-1), model.tts_model.sample_rate
