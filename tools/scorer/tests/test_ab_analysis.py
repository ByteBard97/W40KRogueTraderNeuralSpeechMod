import pytest

from ab_analysis import agreement, binom_p_greater, render, wilson

PAIRS = [{"id": str(i), "axis": "voice" if i < 4 else "emotion"} for i in range(6)]


def test_binom():
    assert binom_p_greater(0, 5) == pytest.approx(1.0)
    assert binom_p_greater(5, 5) == pytest.approx(1 / 32)
    assert binom_p_greater(3, 0) == 1.0


def test_wilson_contains_rate():
    lo, hi = wilson(8, 10)
    assert lo < 0.8 < hi <= 1.0


def test_agreement_excludes_ties_unanswered_and_unpicked():
    ans = {"0": "a", "1": "b", "2": "tie", "3": "a", "4": "a"}       # "5" unanswered
    picks = {"0": "a", "1": "a", "2": "a", "3": None, "4": "a", "5": "b"}
    r = agreement(PAIRS, ans, picks)
    assert r["voice"] == {**r["voice"], "answered": 4, "ties": 1, "decisive": 3, "picker_covered": 2, "agree": 1}
    assert r["voice"]["rate"] == 0.5
    assert r["emotion"]["agree"] == 1 and r["emotion"]["rate"] == 1.0


def test_render_handles_empty():
    assert "nothing comparable" in render("x", agreement(PAIRS, {}, {}))
