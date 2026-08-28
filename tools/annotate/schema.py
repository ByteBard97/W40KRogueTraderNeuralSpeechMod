"""Annotation schema: engine-neutral emotion/delivery labels per dialogue line.

The stored record is deliberately model-agnostic; each TTS backend translates it
(Chatterbox: leading [tags] + exaggeration; Qwen3/Fish: instruct text; Piper/Kokoro: pace only).
"""
from __future__ import annotations

EMOTIONS = ["neutral", "happy", "sad", "angry", "fear", "surprised",
            "sarcastic", "dramatic", "whisper", "commanding", "pleading", "amused"]
NONVERBALS = ["laugh", "chuckle", "sigh", "gasp", "groan", "sniff", "cough", "clear_throat", "shush"]
PACES = ["slow", "normal", "fast"]

JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "guid": {"type": "string"},
                    "emotion": {"type": "string", "enum": EMOTIONS},
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
