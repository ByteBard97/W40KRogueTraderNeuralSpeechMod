"""Higgs TTS 2 adapter (Boson AI, custom Llama-3-derived Community License - NOT MIT/Apache,
requires attribution notice in the mod's release files, see PROJECT_PLAN.md). ~11.5GB weights,
3.6B+2.2B params. Comparison/audition candidate only - too large to ship as the in-process
default (see docs/superpowers/plans/2026-09-04-emotional-expressiveness-fix.md discussion), but
useful here to hear the quality ceiling. Requires transformers>=5.3.0 (tools/tts_bakeoff/.venv-higgs,
not the shared .venv-tts, which is pinned older for the other engines)."""
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

MODEL_ID = "bosonai/higgs-tts-2-3b-base"


def load():
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, HiggsAudioV2ForConditionalGeneration
    processor = AutoProcessor.from_pretrained(MODEL_ID, device_map="auto")
    # bf16 alone loads at ~12.7GB, leaving too little headroom on a 16GB card even to encode
    # the reference clip (confirmed via OOM on an RTX 5080) - int8 to fit with room to spare.
    quant_config = BitsAndBytesConfig(load_in_8bit=True)
    model = HiggsAudioV2ForConditionalGeneration.from_pretrained(
        MODEL_ID, device_map="auto", quantization_config=quant_config)
    return processor, model


def synth(ctx, text, prompt_wav=None, prompt_text=None, instruct=None):
    processor, model = ctx
    # The "scene" role is Higgs's documented slot for contextual delivery cues (its own examples
    # use it for things like speaker gender/recording environment) - appending the free-text
    # acting direction there is the best-available mechanism, though unlike Chatterbox's
    # exaggeration/cfg_weight or Fish's inline tags, we don't have hard confirmation this actually
    # steers emotional delivery rather than being read as more scene-setting. Worth an A/B check.
    scene = "Audio is recorded from a quiet room."
    if instruct:
        scene = f"{scene} {instruct}"
    conversation = [
        {"role": "system", "content": [{"type": "text", "text": "Generate audio following instruction."}]},
        {"role": "scene", "content": [{"type": "text", "text": scene}]},
    ]
    if prompt_wav:
        conversation.append({"role": "user", "content": [{"type": "text", "text": prompt_text or ""}]})
        conversation.append({"role": "assistant", "content": [{"type": "audio", "url": str(prompt_wav)}]})
    conversation.append({"role": "user", "content": [{"type": "text", "text": text}]})

    inputs = processor.apply_chat_template(
        conversation, add_generation_prompt=True, tokenize=True, return_dict=True,
        sampling_rate=24000, return_tensors="pt",
    ).to(model.device)

    outputs = model.generate(**inputs, max_new_tokens=1000, do_sample=False)
    decoded = processor.batch_decode(outputs)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.wav"
        processor.save_audio(decoded, str(out_path))
        wav, sr = sf.read(str(out_path), dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    return np.asarray(wav, dtype=np.float32), sr
