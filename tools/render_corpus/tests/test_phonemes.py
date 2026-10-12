import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phonemes import phonemize  # noqa: E402


def test_possessive_and_plain_text():
    out = phonemize("The servitor's last words are drowned out.")
    assert out == "The {S ER1 V IH0 T AH0}'s last words are drowned out."
    assert "SIR" not in out


def test_hyphen_compound_gets_a_space():
    assert "{" in phonemize("a vox-system hummed") and "-" not in phonemize("a vox-system hummed").split("}")[0][-3:]


def test_text_without_lexicon_words_untouched():
    assert phonemize("Nothing special here.") == "Nothing special here."
