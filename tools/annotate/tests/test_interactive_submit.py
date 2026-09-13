import argparse
import hashlib
import json

import pytest

from interactive_submit import (
    SubmitError, find_conversation, required_targets_for_chunk,
    resolve_chunk_params, run, scan_already_labeled_keys, validate_submission,
)

VOCAB = ["resigned", "hopeful", "neutral", "sarcastic"]


def _target(text_key, text="hi", speaker_name="Abelard"):
    return {"guid": text_key, "kind": "cue", "text_key": text_key, "text": text,
            "speaker": {"name": speaker_name}, "voiced": None}


def _label(emotion="resigned", intensity=0.5, pace="normal", nonverbal=None, instruct="x"):
    return {"emotion": emotion, "intensity": intensity, "pace": pace,
            "nonverbal": nonverbal or [], "instruct": instruct}


def _sha1_12(text):
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def test_find_conversation_returns_matching_conv():
    convs = [{"guid": "a"}, {"guid": "b"}]
    assert find_conversation(convs, "b") == {"guid": "b"}


def test_find_conversation_raises_for_unknown_guid():
    with pytest.raises(SubmitError):
        find_conversation([{"guid": "a"}], "missing")


def test_required_targets_for_chunk_filters_by_canonical_chunk():
    targets = [_target("a"), _target("b")]
    ranges = [(0, 50), (40, 90)]
    idxs = [10, 60]  # a canonical to chunk 0, b canonical to chunk 1
    assert [t["text_key"] for t in required_targets_for_chunk(ranges, targets, idxs, 0)] == ["a"]
    assert [t["text_key"] for t in required_targets_for_chunk(ranges, targets, idxs, 1)] == ["b"]


def test_required_targets_for_chunk_rejects_out_of_range_chunk():
    with pytest.raises(SubmitError):
        required_targets_for_chunk([(0, 50)], [_target("a")], [10], chunk=5)


def test_required_targets_for_chunk_rejects_negative_chunk():
    # Without this, a negative chunk would never equal any real canonical_chunk() result
    # (always >= 0), so required silently comes back empty and the eventual error is a
    # confusing "unexpected guids" instead of a clear "chunk does not exist".
    with pytest.raises(SubmitError, match="does not exist"):
        required_targets_for_chunk([(0, 50)], [_target("a")], [10], chunk=-1)


def test_required_targets_for_chunk_excludes_already_labeled_targets():
    # A target already labeled via a different conversation (a cross-conversation
    # duplicate text_key) must not be required here either - see this task's note on
    # why, and context_window.unlabeled_targets in Task 1.
    targets = [_target("a"), _target("b")]
    ranges = [(0, 50)]
    idxs = [10, 20]
    required = required_targets_for_chunk(ranges, targets, idxs, 0, already_labeled={"a"})
    assert [t["text_key"] for t in required] == ["b"]


def test_required_targets_for_chunk_default_already_labeled_is_empty():
    targets = [_target("a")]
    required = required_targets_for_chunk([(0, 50)], targets, [10], 0)
    assert [t["text_key"] for t in required] == ["a"]


def test_validate_submission_happy_path_returns_records_with_text_hash():
    required = [_target("a", text="hello")]
    submitted = {"a": _label()}
    records = validate_submission(submitted, required, VOCAB)
    assert len(records) == 1
    assert records[0]["guid"] == "a"
    assert records[0]["text_hash"] == _sha1_12("hello")


def test_validate_submission_rejects_non_dict_label():
    # {"a": "resigned"} instead of {"a": {"emotion": "resigned", ...}} would otherwise
    # crash on rec.get(...) with an AttributeError instead of a clean SubmitError.
    required = [_target("a")]
    submitted = {"a": "resigned"}
    with pytest.raises(SubmitError, match="JSON object"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_missing_guid():
    required = [_target("a"), _target("b")]
    submitted = {"a": _label()}
    with pytest.raises(SubmitError, match="missing"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_unexpected_guid():
    required = [_target("a")]
    submitted = {"a": _label(), "z": _label()}
    with pytest.raises(SubmitError, match="unexpected"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_emotion_not_in_vocab():
    required = [_target("a")]
    submitted = {"a": _label(emotion="made_up")}
    with pytest.raises(SubmitError, match="vocabulary"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_bad_pace():
    required = [_target("a")]
    submitted = {"a": _label(pace="ludicrous")}
    with pytest.raises(SubmitError, match="pace"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_bad_nonverbal():
    required = [_target("a")]
    submitted = {"a": _label(nonverbal=["screaming"])}
    with pytest.raises(SubmitError, match="nonverbal"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_out_of_range_intensity():
    required = [_target("a")]
    submitted = {"a": _label(intensity=1.5)}
    with pytest.raises(SubmitError, match="intensity"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_boolean_intensity():
    # bool is a subclass of int in Python, so isinstance(True, (int, float)) is True -
    # without an explicit bool check, "intensity": true would silently become 1.0
    # instead of being rejected as the wrong type.
    required = [_target("a")]
    submitted = {"a": _label(intensity=True)}
    with pytest.raises(SubmitError, match="intensity"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_null_nonverbal():
    # rec.get("nonverbal", []) only supplies the default when the key is missing -
    # an explicit "nonverbal": null returns None, and iterating over it used to raise
    # a raw TypeError instead of a clean SubmitError.
    required = [_target("a")]
    submitted = {"a": _label()}
    submitted["a"]["nonverbal"] = None
    with pytest.raises(SubmitError, match="nonverbal"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_empty_instruct():
    required = [_target("a")]
    submitted = {"a": _label(instruct="")}
    with pytest.raises(SubmitError, match="instruct"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_too_long_instruct():
    required = [_target("a")]
    submitted = {"a": _label(instruct="x" * 301)}
    with pytest.raises(SubmitError, match="300"):
        validate_submission(submitted, required, VOCAB)


def test_scan_already_labeled_keys_reads_every_cache_file(tmp_path):
    (tmp_path / "conv1.json").write_text(json.dumps({
        "conv": "conv1", "model": "m", "lines": [{"guid": "a", "emotion": "resigned"}],
    }), encoding="utf-8")
    (tmp_path / "conv2__chunk0.json").write_text(json.dumps({
        "conv": "conv2", "model": "m", "lines": [{"guid": "b", "emotion": "resigned"}],
        "chunk_size": 50, "chunk_overlap": 10,
    }), encoding="utf-8")
    assert scan_already_labeled_keys(tmp_path) == {"a", "b"}


def test_scan_already_labeled_keys_excludes_given_path(tmp_path):
    # Resubmitting/correcting the same chunk must not see its own about-to-be-
    # overwritten file as "already labeled elsewhere", or every key in it becomes
    # unexpected on the very next resubmission attempt.
    target_path = tmp_path / "conv1.json"
    target_path.write_text(json.dumps({
        "conv": "conv1", "model": "m", "lines": [{"guid": "a", "emotion": "resigned"}],
    }), encoding="utf-8")
    assert scan_already_labeled_keys(tmp_path, exclude_path=target_path) == set()


def test_resolve_chunk_params_uses_cli_when_no_existing_chunks(tmp_path):
    assert resolve_chunk_params(tmp_path, "conv1", 50, 10) == (50, 10)


def test_resolve_chunk_params_reuses_recorded_values(tmp_path):
    (tmp_path / "conv1__chunk0.json").write_text(json.dumps({
        "conv": "conv1", "model": "claude-interactive", "lines": [],
        "chunk_size": 30, "chunk_overlap": 5,
    }), encoding="utf-8")
    assert resolve_chunk_params(tmp_path, "conv1", 50, 10) == (30, 5)


def _args(**overrides):
    defaults = dict(conv_guid="conv1", json_file=None, cache_dir=None, chunk=0,
                     chunk_size=50, chunk_overlap=10, input=None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_run_rejects_malformed_json_with_a_clean_error_not_a_traceback(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "TestConv", "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text("{not valid json", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    with pytest.raises(SubmitError, match="not valid JSON"):
        run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))
    assert not (cache_dir / "conv1.json").exists()


def test_run_rejects_a_json_list_instead_of_an_object(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "TestConv", "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text("[1, 2, 3]", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    with pytest.raises(SubmitError, match="expected a JSON object"):
        run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))


def test_run_writes_unchunked_cache_file_for_small_conversation(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "TestConv",
        "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"a": _label()}), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))

    out = json.loads((cache_dir / "conv1.json").read_text(encoding="utf-8"))
    assert out["conv"] == "conv1"
    assert out["model"] == "claude-interactive"
    assert out["lines"][0]["guid"] == "a"
    assert out["lines"][0]["text_hash"] == _sha1_12("hello")
    assert "chunk_size" not in out


def test_run_writes_chunked_cache_file_with_chunk_params_recorded(tmp_path):
    lines = [_target(f"key{i}", text=f"line {i}", speaker_name="Idira") for i in range(120)]
    lines[10] = _target("key10", text="line 10")   # Abelard - lands in chunk range (0, 50)
    lines[100] = _target("key100", text="line 100")  # Abelard - lands in chunk range (80, 120)
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{"guid": "conv1", "name": "TestConv", "lines": lines}]),
                           encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"key10": _label()}), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir),
              input=str(convs_path), chunk=0))

    out_path = cache_dir / "conv1__chunk0.json"
    assert out_path.exists()
    out = json.loads(out_path.read_text(encoding="utf-8"))
    assert out["chunk_size"] == 50
    assert out["chunk_overlap"] == 10
    assert out["lines"][0]["guid"] == "key10"


def test_run_excludes_target_already_labeled_in_a_different_conversation(tmp_path):
    # Reproduces the real corpus shape (e.g. AlternativeLordCaptains_dialogue /
    # AlternativeLordCaptains_Fem_dialogue sharing three text_keys): "sharedkey" was
    # already labeled while working through conv1; conv2 reuses the same text_key
    # alongside its own "onlyinconv2" - submitting conv2 must not require "sharedkey"
    # again, and must not choke trying to write a second copy of it.
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([
        {"guid": "conv1", "name": "Conv1", "lines": [_target("sharedkey", text="shared")]},
        {"guid": "conv2", "name": "Conv2", "lines": [
            _target("sharedkey", text="shared"),
            _target("onlyinconv2", text="only here"),
        ]},
    ]), encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "conv1.json").write_text(json.dumps({
        "conv": "conv1", "model": "claude-interactive",
        "lines": [{"guid": "sharedkey", "emotion": "resigned", "intensity": 0.4,
                   "pace": "normal", "nonverbal": [], "instruct": "x", "text_hash": "x"}],
    }), encoding="utf-8")

    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"onlyinconv2": _label()}), encoding="utf-8")

    run(_args(conv_guid="conv2", json_file=str(submitted_path),
              cache_dir=str(cache_dir), input=str(convs_path)))

    out = json.loads((cache_dir / "conv2.json").read_text(encoding="utf-8"))
    assert [line["guid"] for line in out["lines"]] == ["onlyinconv2"]


def test_run_resubmitting_same_chunk_does_not_treat_its_own_prior_output_as_a_conflict(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "Conv1", "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # A prior (imperfect) submission already exists for this exact chunk.
    (cache_dir / "conv1.json").write_text(json.dumps({
        "conv": "conv1", "model": "claude-interactive",
        "lines": [{"guid": "a", "emotion": "resigned", "intensity": 0.3,
                   "pace": "slow", "nonverbal": [], "instruct": "old", "text_hash": "x"}],
    }), encoding="utf-8")

    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"a": _label(emotion="hopeful")}), encoding="utf-8")

    run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))

    out = json.loads((cache_dir / "conv1.json").read_text(encoding="utf-8"))
    assert out["lines"][0]["emotion"] == "hopeful"  # corrected value, not silently skipped
