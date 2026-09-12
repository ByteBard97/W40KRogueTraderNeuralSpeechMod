"""Builds the emotion-labeling prompt sent to an audio-input LLM, and a stable hash of
the prompt template (independent of any per-clip transcript) used to key cached output."""
from __future__ import annotations

import hashlib

_TRANSCRIPT_PLACEHOLDER = "{TRANSCRIPT}"

_INSTRUCTIONS = """You are labeling the emotional delivery of a short voiced game line.

Listen to the audio and pick exactly 3 words that best describe how the speaker sounds,
ranked best-fit first, preferably from this vocabulary (grouped by energy level):

{vocab_block}

Respond with ONLY this JSON object, no other text:
{{"labels": [{{"word": "...", "confidence": 0.0}}, {{"word": "...", "confidence": 0.0}}, {{"word": "...", "confidence": 0.0}}], "notes": ""}}

confidence is your certainty in that pick, from 0.0 to 1.0. If none of the 3 vocabulary
words you'd normally pick fit well, use "notes" to propose a better word instead — still
return exactly 3 labels."""


def _vocab_block(vocab: dict) -> str:
    lines = []
    for tier in vocab["tiers"]:
        lines.append(f"{tier['tier']}: {', '.join(tier['words'])}")
    return "\n".join(lines)


def build_prompt(vocab: dict, mode: str, transcript: str | None) -> str:
    if mode not in ("audio", "audio+text"):
        raise ValueError(f"unknown mode: {mode!r}")
    if mode == "audio+text" and transcript is None:
        raise ValueError("audio+text mode requires a transcript")
    text = _INSTRUCTIONS.format(vocab_block=_vocab_block(vocab))
    if mode == "audio+text":
        text += f'\n\nTranscript of the line: "{transcript}"'
    return text


def prompt_hash(vocab: dict, mode: str) -> str:
    transcript = _TRANSCRIPT_PLACEHOLDER if mode == "audio+text" else None
    template = build_prompt(vocab, mode, transcript)
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]
