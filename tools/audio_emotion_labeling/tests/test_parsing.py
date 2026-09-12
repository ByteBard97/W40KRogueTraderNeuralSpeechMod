from parsing import parse_model_response


def test_parses_clean_json():
    raw = '{"labels": [{"word": "rueful", "confidence": 0.8}, {"word": "sad", "confidence": 0.4}, {"word": "grim", "confidence": 0.2}], "notes": ""}'
    result = parse_model_response(raw)
    assert result["labels"][0] == {"word": "rueful", "confidence": 0.8}
    assert len(result["labels"]) == 3
    assert result["notes"] == ""


def test_recovers_json_wrapped_in_prose():
    raw = ('Sure, here is my analysis:\n'
           '{"labels": [{"word": "commanding", "confidence": 0.9}], "notes": "firm"}\n'
           'Let me know if you need anything else!')
    result = parse_model_response(raw)
    assert result["labels"] == [{"word": "commanding", "confidence": 0.9}]
    assert result["notes"] == "firm"


def test_truncated_json_returns_none():
    raw = '{"labels": [{"word": "angry", "confidence": 0.7}, {"word": "stern"'
    assert parse_model_response(raw) is None


def test_missing_labels_key_returns_none():
    raw = '{"notes": "the speaker sounds tired"}'
    assert parse_model_response(raw) is None


def test_drops_malformed_label_entries_but_keeps_valid_ones():
    raw = '{"labels": [{"word": "angry", "confidence": 0.7}, {"word": 123}, "not a dict"], "notes": ""}'
    result = parse_model_response(raw)
    assert result["labels"] == [{"word": "angry", "confidence": 0.7}]


def test_clamps_out_of_range_confidence():
    raw = '{"labels": [{"word": "angry", "confidence": 1.7}], "notes": ""}'
    result = parse_model_response(raw)
    assert result["labels"][0]["confidence"] == 1.0


def test_picks_real_answer_over_an_earlier_echoed_example():
    # Small models sometimes echo part of the instruction's own example JSON before
    # giving the real answer. A naive "first { to last }" span would swallow both
    # objects plus the prose between them and fail to parse at all.
    raw = ('Example format: {"labels": [{"word": "example", "confidence": 0.5}], "notes": ""} '
           'Now here is my actual answer: '
           '{"labels": [{"word": "commanding", "confidence": 0.85}], "notes": "firm"}')
    result = parse_model_response(raw)
    assert result["labels"] == [{"word": "commanding", "confidence": 0.85}]
    assert result["notes"] == "firm"


def test_ignores_unrelated_brace_pair_before_the_real_object():
    raw = ('Confidence is like a score in the {0,1} range. '
           '{"labels": [{"word": "angry", "confidence": 0.7}], "notes": ""}')
    result = parse_model_response(raw)
    assert result["labels"] == [{"word": "angry", "confidence": 0.7}]
