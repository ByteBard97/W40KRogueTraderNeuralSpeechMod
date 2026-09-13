import serve


def test_clip_agreement_uses_ser_when_the_emotion_is_ser_mappable(monkeypatch):
    monkeypatch.setitem(serve.SER_SCORES, "EVT_1", {"label": "angry", "confidence": 0.9})
    assert serve.clip_agreement("EVT_1", "angry", serve.SER_SCORES["EVT_1"]) == "agree"
    assert serve.clip_agreement("EVT_1", "sad", serve.SER_SCORES["EVT_1"]) == "disagree"


def test_clip_agreement_falls_back_to_ultravox_audio_mode_when_ser_has_no_equivalent(monkeypatch):
    # "resigned" isn't one of the 6 words emotion2vec+ can recognize (EMOTION_TO_SER), so SER
    # (even if present) can't confirm or deny it - the only real cross-check available is
    # whether Ultravox's audio-only pass agrees with the audio+text pass that assigned this
    # clip to "resigned" in the first place.
    monkeypatch.setitem(serve.AUDIO_LLM_LABELS, "EVT_2", {
        "ultravox": {"audio": {"h1": {"parse_ok": True, "labels": [{"word": "resigned", "confidence": 0.8}]}}}
    })
    assert serve.clip_agreement("EVT_2", "resigned", ser=None) == "agree"
    assert serve.clip_agreement("EVT_2", "hopeful", ser=None) == "disagree"


def test_clip_agreement_is_na_when_no_check_is_possible_at_all(monkeypatch):
    monkeypatch.setitem(serve.AUDIO_LLM_LABELS, "EVT_3", {})
    assert serve.clip_agreement("EVT_3", "resigned", ser=None) == "n/a"


def test_clip_agreement_ignores_unparsed_ultravox_predictions(monkeypatch):
    monkeypatch.setitem(serve.AUDIO_LLM_LABELS, "EVT_4", {
        "ultravox": {"audio": {"h1": {"parse_ok": False, "labels": []}}}
    })
    assert serve.clip_agreement("EVT_4", "resigned", ser=None) == "n/a"
