# tools/audio_emotion_labeling/tests/test_scoring.py
from scoring import tier_similarity, recall_at_k, best_of_set_similarity

WORD_TO_TIER = {
    "rueful": "Low-mid energy", "somber": "Low energy", "grim": "Mid energy",
    "ecstatic": "High energy", "angry": "Original", "commanding": "Original",
}


def test_tier_similarity_exact_word_is_one():
    assert tier_similarity("rueful", "rueful", WORD_TO_TIER) == 1.0


def test_tier_similarity_same_tier_is_point_seven():
    assert tier_similarity("angry", "commanding", WORD_TO_TIER) == 0.7


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
