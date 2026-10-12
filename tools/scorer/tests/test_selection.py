import pytest

from selection import (VOICE_FEATURES, passes_gates, plan_retakes, review_queue, select_winners,
                       take_key, voice_composite)

SCALE = {f: 1.0 for f in VOICE_FEATURES}


def row(v=1.0, wer=0.0, clipped=False, trail=0.2, p=0.5):
    r = {f: v / len(VOICE_FEATURES) for f in VOICE_FEATURES}
    r.update(wer=wer, clipped=clipped, trail_silence=trail, p_target_family=p, target_family="stern")
    return r


def setup(rows_by_guid):
    manifest, scores = [], {}
    for guid, rows in rows_by_guid.items():
        for t, r in enumerate(rows):
            manifest.append({"guid": guid, "take": t, "text": "hi", "emotion": "stern", "wav": f"{guid}/{t}.wav"})
            scores[take_key(guid, t)] = r
    return manifest, scores


def test_voice_composite_divides_by_scale():
    rows = [row(2.0)]
    assert voice_composite(rows, {f: 2.0 for f in VOICE_FEATURES})[0] == pytest.approx(1.0)


@pytest.mark.parametrize("kw,ok", [({}, True), ({"wer": 0.5}, False), ({"clipped": True}, False),
                                    ({"trail": 2.0}, False), ({"wer": 0.34}, True)])
def test_gates(kw, ok):
    assert passes_gates(row(**kw)) is ok


def test_winner_is_best_passing_take_not_best_overall():
    m, s = setup({"a": [row(1.0), row(5.0, wer=0.9), row(3.0)]})
    w = select_winners(m, s, SCALE)["a"]
    assert w["status"] == "ok" and w["take"] == 2 and w["n_pass"] == 2 and w["n_takes"] == 3


def test_no_passing_take():
    m, s = setup({"a": [row(wer=1.0), row(clipped=True)]})
    w = select_winners(m, s, SCALE)["a"]
    assert w["status"] == "no_passing_take" and "needs_more_takes" in w["flags"]


def test_unscored_takes_ignored():
    m, s = setup({"a": [row(1.0), row(2.0)]})
    del s[take_key("a", 1)]
    assert select_winners(m, s, SCALE)["a"]["n_takes"] == 1


def test_flags():
    m, s = setup({"a": [row(1.0, p=0.01), row(2.0, p=0.01)]})
    f = select_winners(m, s, SCALE)["a"]["flags"]
    assert "few_candidates" in f and "low_emotion_prob" in f
    m, s = setup({"b": [row(1.0 + i, p=0.9) for i in range(4)]})
    assert select_winners(m, s, SCALE)["b"]["flags"] == []


def test_missing_probability_is_not_flagged():
    m, s = setup({"a": [row(1.0, p=None)] * 4})
    assert "low_emotion_prob" not in select_winners(m, s, SCALE)["a"]["flags"]


def test_plan_retakes():
    winners = {"ok": {"n_pass": 3, "n_takes": 6}, "few": {"n_pass": 1, "n_takes": 6},
               "capped": {"n_pass": 0, "n_takes": 12}, "none": {"n_pass": 0, "n_takes": 6}}
    assert plan_retakes(winners, ["ok", "few", "capped", "none", "unscored"], 2, 12) == ["few", "none", "unscored"]


def test_review_queue_reasons():
    m, s = setup({"good": [row(1.0 + 2 * i, p=0.9) for i in range(4)],
                  "bad": [row(wer=1.0)],
                  "same": [row(1.0, p=0.9)] * 4})
    q = {x["guid"]: x["reasons"] for x in review_queue(select_winners(m, s, SCALE))}
    assert "good" not in q
    assert q["bad"] == ["no_passing_take"]
    assert q["same"] == ["takes_indistinguishable"]
