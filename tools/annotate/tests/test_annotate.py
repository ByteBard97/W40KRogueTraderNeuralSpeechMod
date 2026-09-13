from annotate import build_system, conv_payload, validate


def _line(text_key, speaker_name, text="hi", voiced=None):
    return {"guid": text_key, "kind": "cue", "text_key": text_key, "text": text,
            "speaker": {"name": speaker_name}, "voiced": voiced}


def test_conv_payload_no_filter_keeps_all_lines():
    conv = {"name": "c", "lines": [_line("a", "Abelard"), _line("b", "Idira")]}
    _, lines = conv_payload(conv)
    assert {l["guid"] for l in lines} == {"a", "b"}


def test_conv_payload_speaker_filter_drops_other_speakers():
    conv = {"name": "c", "lines": [_line("a", "Abelard"), _line("b", "Idira")]}
    _, lines = conv_payload(conv, speaker_filter="Abelard")
    assert {l["guid"] for l in lines} == {"a"}


def test_conv_payload_unvoiced_only_drops_lines_with_real_audio():
    conv = {"name": "c", "lines": [
        _line("a", "Abelard", voiced=None),
        _line("b", "Abelard", voiced="SomeCatalogEvent_01"),
    ]}
    _, lines = conv_payload(conv, unvoiced_only=True)
    assert {l["guid"] for l in lines} == {"a"}


def test_conv_payload_combines_speaker_filter_and_unvoiced_only():
    conv = {"name": "c", "lines": [
        _line("a", "Abelard", voiced=None),
        _line("b", "Abelard", voiced="Evt_01"),
        _line("c", "Idira", voiced=None),
    ]}
    _, lines = conv_payload(conv, speaker_filter="Abelard", unvoiced_only=True)
    assert {l["guid"] for l in lines} == {"a"}


def test_conv_payload_no_matching_lines_returns_empty():
    conv = {"name": "c", "lines": [_line("a", "Idira")]}
    user, lines = conv_payload(conv, speaker_filter="Abelard")
    assert user == "" and lines == []


def test_validate_falls_back_to_neutral_for_unknown_emotion():
    lines = [{"guid": "a", "text": "hi"}]
    result = {"lines": [{"guid": "a", "emotion": "made_up", "intensity": 0.5,
                          "pace": "normal", "nonverbal": [], "instruct": "x"}]}
    out = validate(result, lines, emotions=["neutral", "angry"])
    assert out[0]["emotion"] == "neutral"


def test_validate_falls_back_to_first_word_when_neutral_not_in_vocab():
    lines = [{"guid": "a", "text": "hi"}]
    result = {"lines": [{"guid": "a", "emotion": "made_up", "intensity": 0.5,
                          "pace": "normal", "nonverbal": [], "instruct": "x"}]}
    out = validate(result, lines, emotions=["resigned", "hopeful"])
    assert out[0]["emotion"] == "resigned"


def test_validate_keeps_valid_emotion_from_custom_vocab():
    lines = [{"guid": "a", "text": "hi"}]
    result = {"lines": [{"guid": "a", "emotion": "resigned", "intensity": 0.5,
                          "pace": "normal", "nonverbal": [], "instruct": "x"}]}
    out = validate(result, lines, emotions=["resigned", "hopeful"])
    assert out[0]["emotion"] == "resigned"


def test_build_system_embeds_given_emotions():
    prompt = build_system(["resigned", "hopeful"])
    assert "resigned" in prompt and "hopeful" in prompt
