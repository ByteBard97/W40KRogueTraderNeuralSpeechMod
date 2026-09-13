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


import json

from annotate import merge_cache_dirs


def _write_cache_file(path, conv_guid, text_key, emotion):
    path.write_text(json.dumps({
        "conv": conv_guid, "model": "test",
        "lines": [{"guid": text_key, "emotion": emotion, "intensity": 0.5,
                   "pace": "normal", "nonverbal": [], "instruct": "x", "text_hash": "abc123"}],
    }), encoding="utf-8")


def test_merge_cache_dirs_single_dir(tmp_path):
    d = tmp_path / "cache"
    d.mkdir()
    _write_cache_file(d / "conv1.json", "conv1", "key1", "neutral")
    merged, file_count = merge_cache_dirs([d])
    assert merged["key1"]["emotion"] == "neutral"
    assert file_count == 1


def test_merge_cache_dirs_later_dir_wins_on_conflict(tmp_path):
    d1, d2 = tmp_path / "cache1", tmp_path / "cache2"
    d1.mkdir()
    d2.mkdir()
    _write_cache_file(d1 / "conv1.json", "conv1", "key1", "neutral")
    _write_cache_file(d2 / "conv1.json", "conv1", "key1", "angry")
    merged, _ = merge_cache_dirs([d1, d2])
    assert merged["key1"]["emotion"] == "angry"


def test_merge_cache_dirs_guid_in_only_one_dir_passes_through(tmp_path):
    d1, d2 = tmp_path / "cache1", tmp_path / "cache2"
    d1.mkdir()
    d2.mkdir()
    _write_cache_file(d1 / "conv1.json", "conv1", "key1", "neutral")
    _write_cache_file(d2 / "conv2.json", "conv2", "key2", "angry")
    merged, _ = merge_cache_dirs([d1, d2])
    assert merged["key1"]["emotion"] == "neutral"
    assert merged["key2"]["emotion"] == "angry"


def test_merge_cache_dirs_duplicate_guid_within_one_dir_is_deterministic_by_filename(tmp_path):
    # Regression test for the sorted() fix - mirrors cache_merged's real 1,680 duplicate
    # text_keys, where today's merge picks an arbitrary winner. sorted() processes
    # conv_a.json before conv_z.json, so conv_z's value (processed last) always wins,
    # regardless of the order the files happened to be created on disk.
    d = tmp_path / "cache"
    d.mkdir()
    _write_cache_file(d / "conv_z.json", "conv_z", "dupkey", "angry")
    _write_cache_file(d / "conv_a.json", "conv_a", "dupkey", "sad")
    merged, _ = merge_cache_dirs([d])
    assert merged["dupkey"]["emotion"] == "angry"
