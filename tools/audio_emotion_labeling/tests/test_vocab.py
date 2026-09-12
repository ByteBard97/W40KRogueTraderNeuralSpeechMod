import json
from pathlib import Path

from vocab import load_vocab, ENERGY_LADDER


def test_load_vocab_merges_original_and_custom_tiers(tmp_path):
    custom_path = tmp_path / "custom_emotions.json"
    custom_path.write_text(json.dumps({"tiers": [
        {"tier": "Low energy", "words": ["somber", "resigned"]},
        {"tier": "High energy", "words": ["ecstatic"]},
    ]}))

    vocab = load_vocab(custom_path)

    assert vocab["tiers"][0]["tier"] == "Original"
    assert "angry" in vocab["tiers"][0]["words"]
    assert vocab["word_to_tier"]["angry"] == "Original"
    assert vocab["word_to_tier"]["somber"] == "Low energy"
    assert "somber" in vocab["all_words"]
    assert len(vocab["all_words"]) == 12 + 2 + 1


def test_load_vocab_missing_file_returns_original_only(tmp_path):
    vocab = load_vocab(tmp_path / "does_not_exist.json")
    assert vocab["tiers"] == [{"tier": "Original", "words": vocab["tiers"][0]["words"]}]
    assert len(vocab["all_words"]) == 12


def test_energy_ladder_is_five_tiers_in_order():
    assert ENERGY_LADDER == ["Low energy", "Low-mid energy", "Mid energy",
                              "Mid-high energy", "High energy"]
