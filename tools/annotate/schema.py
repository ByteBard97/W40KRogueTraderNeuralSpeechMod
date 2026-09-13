"""Annotation schema: engine-neutral emotion/delivery labels per dialogue line.

The stored record is deliberately model-agnostic; each TTS backend translates it
(Chatterbox: leading [tags] + exaggeration; Qwen3/Fish: instruct text; Piper/Kokoro: pace only).
"""
from __future__ import annotations

EMOTIONS = ["neutral", "happy", "sad", "angry", "fear", "surprised",
            "sarcastic", "dramatic", "whisper", "commanding", "pleading", "amused"]
NONVERBALS = ["laugh", "chuckle", "sigh", "gasp", "groan", "sniff", "cough", "clear_throat", "shush"]
PACES = ["slow", "normal", "fast"]


def build_json_schema(emotions: list[str]) -> dict:
    """Same schema as the module-level default, but with the emotion enum swapped for a
    caller-supplied vocabulary - see tools/audio_emotion_labeling/build_speaker_vocab.py,
    which derives a per-speaker vocabulary wider than this module's fixed 12 words."""
    return {
        "type": "object",
        "properties": {
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "guid": {"type": "string"},
                        "emotion": {"type": "string", "enum": emotions},
                        "intensity": {"type": "number", "minimum": 0, "maximum": 1},
                        "pace": {"type": "string", "enum": PACES},
                        "nonverbal": {"type": "array", "items": {"type": "string", "enum": NONVERBALS}},
                        "instruct": {"type": "string", "maxLength": 300},
                    },
                    "required": ["guid", "emotion", "intensity", "pace", "nonverbal", "instruct"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["lines"],
        "additionalProperties": False,
    }


JSON_SCHEMA = build_json_schema(EMOTIONS)
