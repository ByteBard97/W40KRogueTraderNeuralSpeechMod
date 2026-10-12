import json

import pytest

from judge_logic import (argmax, classification_metrics, consistent_verdict, mean_logprobs, pair_agreement,
                         pair_prompt, parse_choice, position_bias, prior_correct, read_jsonl, single_prompt, wilson)

FAMS = ["stern", "warm", "angry"]
DESC = {"stern": "s", "warm": "w", "angry": "a"}


def test_single_prompt_lists_families_and_optional_transcript():
    p = single_prompt(FAMS, DESC, "Hello there")
    assert '- "warm": w' in p and 'Transcript of the line: "Hello there"' in p
    assert "Transcript" not in single_prompt(FAMS, DESC)


def test_pair_prompt_axes():
    assert "SAME PERSON" in pair_prompt("voice")
    e = pair_prompt("emotion", "relieved", "warm tone")
    assert '"relieved" (warm tone)' in e and "SAME PERSON" not in e


@pytest.mark.parametrize("raw,exp", [('{"family": "warm"}', "warm"), ('x {"family":"stern"} y', "stern"),
                                     ('{"family": "purple"}', None), ("nonsense", None), ("", None), (None, None)])
def test_parse_choice(raw, exp):
    assert parse_choice(raw, FAMS) == exp


def test_prior_correction_undoes_collapse():
    rows = [{"stern": -0.1, "warm": -3.0, "angry": -3.0}] * 9 + [{"stern": -0.7, "warm": -1.0, "angry": -4.0}]
    prior = mean_logprobs(rows)
    # the odd clip leans warm relative to the model's habit, despite stern still being the raw max
    assert argmax(rows[-1]) == "stern"
    assert argmax(prior_correct(rows[-1], prior)) == "warm"


def test_metrics():
    truth = ["stern", "stern", "warm", "angry"]
    pred = ["stern", "warm", "warm", None]
    m = classification_metrics(truth, pred, FAMS)
    assert m["top1"] == 0.5 and m["parse_failures"] == 1 and m["majority_baseline"] == 0.5
    assert m["recall"] == {"stern": 0.5, "warm": 1.0, "angry": 0.0}
    assert m["macro_recall"] == pytest.approx(0.5) and m["families_recall_over_0.3"] == 2


@pytest.mark.parametrize("ab,ba,exp", [("A", "B", "a"), ("B", "A", "b"), ("A", "A", None), ("B", "B", None),
                                       (None, "A", None), ("A", "?", None)])
def test_consistent_verdict(ab, ba, exp):
    assert consistent_verdict(ab, ba) == exp


def test_position_bias():
    assert position_bias(["A"] * 9 + ["B"]) == 0.9
    assert position_bias(["A", "B"]) == 0.5
    assert position_bias([None]) == 0.0


def test_pair_agreement():
    verdicts = {"1": "a", "2": "b", "3": None, "4": "a", "5": "a"}
    human = {"1": "a", "2": "a", "3": "b", "4": "tie", "5": "b"}
    axes = {"1": "emotion", "2": "emotion", "3": "emotion", "4": "voice", "5": "voice"}
    r = pair_agreement(verdicts, human, axes)
    assert r["emotion"] == {"human_decisive": 3, "judge_consistent": 2, "agree": 1, "agreement": 0.5,
                            "consistent_fraction": pytest.approx(2 / 3)}
    assert r["voice"]["human_decisive"] == 1 and r["voice"]["agreement"] == 0.0


def test_wilson_bounds():
    lo, hi = wilson(50, 100)
    assert lo < 0.5 < hi and wilson(0, 0) == (0.0, 1.0)


def test_read_jsonl(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"a": 1}) + "\n\n" + json.dumps({"a": 2}) + "\n")
    assert [r["a"] for r in read_jsonl(p)] == [1, 2] and read_jsonl(tmp_path / "none") == []


def test_choice_logprobs_finds_token_after_marker():
    content = [{"token": '{"', "logprob": 0, "top_logprobs": []},
               {"token": 'family', "logprob": 0, "top_logprobs": []},
               {"token": '": "', "logprob": 0, "top_logprobs": []},
               {"token": "st", "logprob": -0.2, "top_logprobs": [
                   {"token": "st", "logprob": -0.2}, {"token": "w", "logprob": -2.0}, {"token": "a", "logprob": -3.0}]}]
    from judge_logic import choice_logprobs
    r = choice_logprobs(content, ["stern", "warm", "angry"], '{"family": "')
    assert r == {"stern": -0.2, "warm": -2.0, "angry": -3.0}
    assert choice_logprobs(content, ["stern", "zzz"], '{"family": "') is None
    assert choice_logprobs(content[:2], ["stern"], '{"family": "') is None
