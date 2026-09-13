"""Builds a per-speaker emotion vocabulary from cross-mode agreement in
audio_llm_labels.json.

A word qualifies only if it appears in the top-k picks of BOTH the audio-only and
audio+text Ultravox passes for the same clip, at least `threshold` times across the
speaker's catalog. Label confidence is deliberately NOT used as a gate: the pilot
report (data/voices/emotion_banks/pilot_report.md) shows Ultravox's confidence values
are near-constant per rank (0.8/0.6/0.4) regardless of clip, and mean confidence on
agreement (0.80) vs disagreement (0.83) shows it carries no correctness signal."""
from __future__ import annotations

from collections import Counter


def _top_words(entry: dict | None, top_k: int, valid_words: set[str]) -> list[str]:
    if not entry:
        return []
    return [l["word"] for l in entry.get("labels", [])[:top_k] if l["word"] in valid_words]


def event_agreement_words(audio_entry: dict | None, audio_text_entry: dict | None,
                           valid_words: set[str], top_k: int = 2) -> set[str]:
    """Words in the top-k of BOTH modes for one clip, restricted to valid_words (filters
    transcript-echo parsing artifacts like 'fertile' or 'sister argenta' that aren't real
    vocabulary picks)."""
    audio_words = set(_top_words(audio_entry, top_k, valid_words))
    text_words = set(_top_words(audio_text_entry, top_k, valid_words))
    return audio_words & text_words


def build_agreement_counts(speaker_labels: dict, valid_words: set[str],
                            top_k: int = 2) -> tuple[Counter, dict[str, list[str]]]:
    """speaker_labels: event -> {"audio": entry_or_None, "audio+text": entry_or_None}.
    Returns (word -> agreement count, word -> [events exhibiting it]) across the
    speaker's whole catalog."""
    counts: Counter = Counter()
    examples: dict[str, list[str]] = {}
    for event, modes in speaker_labels.items():
        for word in event_agreement_words(modes.get("audio"), modes.get("audio+text"), valid_words, top_k):
            counts[word] += 1
            examples.setdefault(word, []).append(event)
    return counts, examples


def select_vocab(counts: Counter, threshold: int) -> list[str]:
    """Words meeting the agreement threshold, most-frequent first then alphabetical."""
    return sorted((w for w, c in counts.items() if c >= threshold), key=lambda w: (-counts[w], w))
