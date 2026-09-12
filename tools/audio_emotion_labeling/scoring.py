"""Pure scoring functions comparing a model's predicted labels against a human label.
Ground truth here is soft (the human was often unsure between several plausible words),
so similarity is graded via the project's own energy tiers rather than exact match only."""
from __future__ import annotations

from vocab import ENERGY_LADDER


def tier_similarity(word_a: str, word_b: str, word_to_tier: dict[str, str]) -> float:
    if word_a == word_b:
        return 1.0
    tier_a, tier_b = word_to_tier.get(word_a), word_to_tier.get(word_b)
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
