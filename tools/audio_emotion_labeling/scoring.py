"""Pure scoring functions comparing a model's predicted labels against a human label.
Ground truth here is soft (the human was often unsure between several plausible words),
so similarity is graded via the project's own energy tiers rather than exact match only."""
from __future__ import annotations

from vocab import ENERGY_LADDER

# vocab.py's "Original" (the 12-word legacy enum) and "Custom" (ad hoc /add_emotion
# additions) tiers predate the 5-level energy-tier system and were never placed on it, so
# tier_similarity could never award partial credit against them - e.g. "commanding" vs
# "firm" scored a flat 0.0 despite being close synonyms, since "Original" isn't adjacent
# to anything. This maps each of those words onto its nearest energy tier, by comparison
# to its neighbors in custom_emotions.json, for scoring purposes only - it does not change
# vocab.py's actual tier assignment or the prompt text sent to the model. "Register
# modifiers" words (quiet, clipped, hushed...) are deliberately left unmapped: they're
# vocal delivery/manner, a genuinely separate axis from emotion, not values on this
# ladder - and, unlike the words below, none of them are ever a valid emotion pick in the
# first place (only EMOTION_ORDER/Custom words are). "whisper" IS one of those valid
# picks despite also describing delivery, so it still needs a placement; Low energy
# (alongside somber/hollow/numb) fits its withdrawn, subdued connotation as an emotion.
_LEGACY_ENERGY_OVERRIDE = {
    "angry": "High energy", "fear": "High energy", "pleading": "High energy",
    "commanding": "Mid energy", "surprised": "Mid-high energy", "dramatic": "Mid-high energy",
    "happy": "Mid energy", "amused": "Mid energy", "neutral": "Mid energy", "hopeful": "Mid energy",
    "sarcastic": "Low-mid energy", "skeptical": "Low-mid energy",
    "sad": "Low energy", "whisper": "Low energy",
}


def _effective_tier(word: str, word_to_tier: dict[str, str]) -> str | None:
    return _LEGACY_ENERGY_OVERRIDE.get(word, word_to_tier.get(word))


def tier_similarity(word_a: str, word_b: str, word_to_tier: dict[str, str]) -> float:
    if word_a == word_b:
        return 1.0
    tier_a, tier_b = _effective_tier(word_a, word_to_tier), _effective_tier(word_b, word_to_tier)
    if tier_a is None or tier_b is None:
        return 0.0
    if tier_a == tier_b:
        return 0.7
    if tier_a in ENERGY_LADDER and tier_b in ENERGY_LADDER:
        if abs(ENERGY_LADDER.index(tier_a) - ENERGY_LADDER.index(tier_b)) == 1:
            return 0.4
    return 0.0


def recall_at_k(human_word: str, model_words: list[str], k: int) -> bool:
    return human_word in model_words[:k]


def best_of_set_similarity(human_word: str, model_words: list[str], word_to_tier: dict[str, str]) -> float:
    if not model_words:
        return 0.0
    return max(tier_similarity(human_word, w, word_to_tier) for w in model_words)
