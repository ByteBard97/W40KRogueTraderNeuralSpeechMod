#!/usr/bin/env python3
"""Generate a designed narrator reference clip with Qwen3-TTS VoiceDesign and register it in
the shared prompt bank (data/voices/prompts/prompts.json) under speaker "narrator".

The game has essentially no voiced pure-narration lines (see PROJECT_PLAN.md), so unlike the
companions there is no real recording to build a narrator prompt from - it has to be designed.
VoiceDesign takes a natural-language description and speaks arbitrary text with no reference
audio at all, so its own output becomes the reference clip for engines that need one
(Qwen3-TTS Base, Fish, IndexTTS) - all fully synthesized, nothing derived from the game.
"""
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data/voices/prompts/narrator"
PROMPTS_PATH = ROOT / "data/voices/prompts/prompts.json"

NARRATOR_TEXT = (
    "The void beyond the hull stretches on, indifferent and vast, "
    "and the crew go about their duties as they always have."
)
NARRATOR_INSTRUCT = (
    "A calm, measured male audiobook narrator: deep, unhurried, precise diction, "
    "a slightly weathered and formal tone, no strong emotion."
)


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def main() -> None:
    import torch
    from qwen_tts import Qwen3TTSModel

    model = Qwen3TTSModel.from_pretrained(
        "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map="cuda:0", dtype=torch.bfloat16)
    wavs, sr = model.generate_voice_design(text=NARRATOR_TEXT, instruct=NARRATOR_INSTRUCT, language="English")
    wav = wavs[0] if isinstance(wavs, (list, tuple)) else wavs

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = OUT_DIR / "01_designed_narrator.wav"
    write_wav(wav_path, np.asarray(wav, dtype=np.float32).reshape(-1), sr)
    duration = len(wav) / sr
    print(f"wrote {wav_path} ({duration:.1f}s @ {sr}Hz)")

    prompts = json.load(open(PROMPTS_PATH, encoding="utf-8")) if PROMPTS_PATH.exists() else {}
    prompts["narrator"] = [{
        "rank": 1, "event": "designed_narrator_v1",
        "wav": str(wav_path.relative_to(ROOT / "data/voices")),
        "text": NARRATOR_TEXT, "duration": round(duration, 2),
        "source": "Qwen3-TTS VoiceDesign, fully synthesized (no game audio)",
    }]
    PROMPTS_PATH.write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"registered narrator prompt in {PROMPTS_PATH}")


if __name__ == "__main__":
    main()
