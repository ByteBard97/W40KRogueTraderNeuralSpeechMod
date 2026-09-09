"""Fish Audio S2 (open weights, non-commercial license) adapter. Free-form natural-language
style tags anywhere in the text (e.g. "[whisper in a small voice]") - not exercised in round 1
(plain-text cloning only, matching the other engines); the annotation_bridge maps our neutral
schema to this format for a later round."""
import sys
from pathlib import Path

import numpy as np
import torch

FISH_DIR = Path(__file__).resolve().parent.parent.parent / "reference/fish-speech"
CHECKPOINT_DIR = FISH_DIR / "checkpoints/s2-pro"


def load():
    sys.path.insert(0, str(FISH_DIR))
    from fish_speech.inference_engine import TTSInferenceEngine
    from fish_speech.models.dac.inference import load_model as load_decoder_model
    from fish_speech.models.text2semantic.inference import launch_thread_safe_queue

    device = "cuda" if torch.cuda.is_available() else "cpu"
    precision = torch.bfloat16

    llama_queue = launch_thread_safe_queue(
        checkpoint_path=CHECKPOINT_DIR, device=device, precision=precision, compile=False)
    # The semantic LLM alone loads at ~11.9GB - not enough headroom left on a 16GB card for the
    # DAC decoder too. It's much smaller/cheaper than the 36-layer LLM, so run it on CPU instead
    # of OOMing trying to fit both on GPU.
    decoder_device = "cpu" if device == "cuda" else device
    decoder_model = load_decoder_model(
        config_name="modded_dac_vq", checkpoint_path=CHECKPOINT_DIR / "codec.pth", device=decoder_device)
    engine = TTSInferenceEngine(llama_queue=llama_queue, decoder_model=decoder_model,
                                compile=False, precision=precision)
    return engine


def synth(engine, text, prompt_wav=None, prompt_text=None, instruct=None):
    from fish_speech.utils.schema import ServeReferenceAudio, ServeTTSRequest

    # S2 officially supports free-form natural-language delivery tags embedded inline in the
    # text, e.g. "[professional broadcast tone]" (reference/fish-speech/docs/en/index.md) - not a
    # fixed vocabulary like Chatterbox's, so the annotation's full instruct sentence can go
    # straight in the brackets.
    if instruct:
        text = f"[{instruct}] {text}"

    references = []
    if prompt_wav:
        references = [ServeReferenceAudio(audio=Path(prompt_wav).read_bytes(), text=prompt_text or "")]
    req = ServeTTSRequest(text=text, references=references, reference_id=None, streaming=False)

    results = list(engine.inference(req))
    final = next(r for r in reversed(results) if r.code == "final")
    sr, audio = final.audio
    return np.asarray(audio, dtype=np.float32).reshape(-1), sr
