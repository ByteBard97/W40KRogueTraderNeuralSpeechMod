"""Qwen2-Audio-7B-Instruct backend adapter: load once, generate per clip."""
from __future__ import annotations

import librosa
import torch
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2AudioForConditionalGeneration

MODEL_ID = "Qwen/Qwen2-Audio-7B-Instruct"
REVISION = "0a095220c30b7b31434169c3086508ef3ea5bf0a"


def load_model():
    processor = AutoProcessor.from_pretrained(MODEL_ID, revision=REVISION)
    try:
        bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
        model = Qwen2AudioForConditionalGeneration.from_pretrained(
            MODEL_ID, revision=REVISION, quantization_config=bnb_config, device_map="auto")
        quant = "4bit-bnb"
    except Exception as e:  # noqa: BLE001 - bnb kernel support on this GPU is unverified
        print(f"4-bit load failed ({e}); falling back to bf16")
        model = Qwen2AudioForConditionalGeneration.from_pretrained(
            MODEL_ID, revision=REVISION, torch_dtype=torch.bfloat16, device_map="auto")
        quant = "bf16"
    return model, processor, {"model_id": MODEL_ID, "quant": quant,
                               "temperature": 0.0, "max_new_tokens": 192}


def generate(model, processor, wav_path: str, prompt_text: str) -> str:
    audio, _ = librosa.load(wav_path, sr=16000, mono=True)
    conversation = [{"role": "user", "content": [
        {"type": "audio", "audio_url": wav_path},
        {"type": "text", "text": prompt_text},
    ]}]
    chat_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=chat_prompt, audio=audio, sampling_rate=16000, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    generated = model.generate(**inputs, max_new_tokens=192, do_sample=False)
    generated = generated[:, inputs["input_ids"].shape[1]:]
    return processor.batch_decode(generated, skip_special_tokens=True)[0]
