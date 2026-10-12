import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from asr_compare import compare  # noqa: E402


def test_clean_take():
    r = compare("The servitor stood in the doorway.", "The servitor stood in the doorway.")
    assert r == {"wer": 0.0, "flags": []}


def test_punctuation_and_case_ignored():
    assert compare("Hello, Lord Captain!", "hello lord captain")["wer"] == 0.0


def test_lexicon_word_mismatch_is_exempt():
    r = compare("The servitor stood still.", "The Tsar Viter stood still.", lex_terms=["servitor"])
    assert r["wer"] == 0.0 and r["flags"] == []


def test_spelled_out_letters_flagged():
    r = compare("The Imperium stood in the doorway.", "The M P E R E M stood in the doorway.")
    assert "asr_spelled" in r["flags"]


def test_truncated_ending():
    r = compare("You must go now before the guards return to the gate.", "You must go now before")
    assert "asr_truncated" in r["flags"] and "asr_bad" in r["flags"]


def test_babble_inserted():
    r = compare("Hold the line.", "Hold the line and then the quick brown fox jumps over a thing.")
    assert "asr_extra_words" in r["flags"]


def test_digits_exempt():
    assert compare("Sector 7 is clear.", "Sector seven is clear.")["wer"] == 0.0
