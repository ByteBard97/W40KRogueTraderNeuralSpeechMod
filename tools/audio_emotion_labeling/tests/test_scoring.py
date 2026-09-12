# tools/audio_emotion_labeling/tests/test_scoring.py
from scoring import tier_similarity, recall_at_k, best_of_set_similarity

WORD_TO_TIER = {
    "rueful": "Low-mid energy", "somber": "Low energy", "grim": "Mid energy",
    "ecstatic": "High energy", "stern": "Mid energy", "firm": "Mid energy",
}


def test_tier_similarity_exact_word_is_one():
    assert tier_similarity("rueful", "rueful", WORD_TO_TIER) == 1.0


def test_tier_similarity_same_tier_is_point_seven():
    assert tier_similarity("stern", "firm", WORD_TO_TIER) == 0.7


def test_tier_similarity_adjacent_energy_tier_is_point_four():
    assert tier_similarity("somber", "rueful", WORD_TO_TIER) == 0.4  # Low <-> Low-mid


def test_tier_similarity_distant_energy_tier_is_zero():
    assert tier_similarity("somber", "ecstatic", WORD_TO_TIER) == 0.0  # Low <-> High


def test_tier_similarity_unknown_word_is_zero():
    assert tier_similarity("somber", "made_up_word", WORD_TO_TIER) == 0.0


def test_recall_at_k_hit_within_k():
    assert recall_at_k("rueful", ["angry", "rueful", "grim"], k=2) is True


def test_recall_at_k_miss_outside_k():
    assert recall_at_k("rueful", ["angry", "grim", "rueful"], k=2) is False


def test_best_of_set_similarity_takes_max():
    result = best_of_set_similarity("rueful", ["angry", "somber", "ecstatic"], WORD_TO_TIER)
    assert result == 0.4  # somber is adjacent-tier to rueful; angry/ecstatic score lower


def test_best_of_set_similarity_empty_set_is_zero():
    assert best_of_set_similarity("rueful", [], WORD_TO_TIER) == 0.0


# --- legacy-word energy override: real vocab.py "Original"/"Custom" words that predate
# the energy-tier system and previously scored a flat 0.0 against any real-tier word no
# matter how close a synonym, since "Original"/"Custom" were never on the ladder ---

def test_legacy_word_gets_same_tier_credit_against_real_neighbor():
    # "commanding" (Original enum, overridden to Mid energy) vs "firm" (a real Mid-energy
    # vocab word) - same effective tier. This is the exact pair that first surfaced the
    # scoring gap (previously scored a flat 0.0 despite being close synonyms).
    assert tier_similarity("commanding", "firm", {"firm": "Mid energy"}) == 0.7


def test_legacy_word_gets_partial_credit_against_adjacent_real_tier():
    # "commanding" (Mid energy) vs "defiant" (a real Mid-high-energy vocab word) -
    # adjacent tiers, so this gets partial credit instead of the flat 0.0 it scored
    # before the override existed.
    assert tier_similarity("commanding", "defiant", {"defiant": "Mid-high energy"}) == 0.4


def test_pleading_gets_same_tier_credit_against_real_high_energy_neighbor():
    # "pleading" (Original enum, overridden to High energy) vs "desperate" (a real
    # High-energy vocab word) - same effective tier, near-synonyms in practice.
    assert tier_similarity("pleading", "desperate", {"desperate": "High energy"}) == 0.7


def test_two_legacy_words_compare_via_their_overrides():
    # "angry" (High energy) and "commanding" (Mid energy) are both Original-enum words,
    # but their overrides are two ladder steps apart - 0.0, not the 1.0/0.7 a naive
    # same-bucket view would give two words that both happen to be "Original".
    assert tier_similarity("angry", "commanding", {}) == 0.0
