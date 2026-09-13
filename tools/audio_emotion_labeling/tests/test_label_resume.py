# tools/audio_emotion_labeling/tests/test_label_resume.py
from pathlib import Path

from label import iter_labels
from prompt import prompt_hash
from vocab import load_vocab

VOCAB = load_vocab(Path("/nonexistent"))  # Original tier only, deterministic
CATALOG = {
    "EVT_1": {"speaker": "Abelard", "wav": "wav/Abelard/EVT_1.wav",
              "texts": [{"text": "Hold the line!"}]},
    "EVT_2": {"speaker": "Abelard", "wav": "wav/Abelard/EVT_2.wav",
              "texts": [{"text": "As you wish."}]},
    "EVT_3": {"speaker": "Argenta", "wav": "wav/Argenta/EVT_3.wav",
              "texts": [{"text": "For the Emperor!"}]},
}
BACKEND_META = {"model_id": "fake/model", "quant": "bf16", "temperature": 0.0, "max_new_tokens": 192}


def fake_generate(wav_path: str, prompt_text: str) -> str:
    return '{"labels": [{"word": "angry", "confidence": 0.9}], "notes": ""}'


def test_yields_one_entry_per_unlabeled_event():
    ph = prompt_hash(VOCAB, "audio")
    results = list(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META))
    assert {event for event, _ in results} == {"EVT_1", "EVT_2", "EVT_3"}


def test_skips_events_already_labeled_at_same_key():
    ph = prompt_hash(VOCAB, "audio")
    existing = {"EVT_1": {"qwen2audio": {"audio": {ph: {"labels": []}}}}}
    results = list(iter_labels(CATALOG, existing, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META))
    assert {event for event, _ in results} == {"EVT_2", "EVT_3"}


def test_different_prompt_hash_is_not_skipped():
    old_ph = "aaaaaaaaaaaa"
    new_ph = prompt_hash(VOCAB, "audio")
    existing = {"EVT_1": {"qwen2audio": {"audio": {old_ph: {"labels": []}}}}}
    results = list(iter_labels(CATALOG, existing, "qwen2audio", "audio", new_ph,
                                fake_generate, VOCAB, BACKEND_META))
    assert "EVT_1" in {event for event, _ in results}


def test_event_filter_restricts_to_the_given_event_names():
    ph = prompt_hash(VOCAB, "audio")
    results = list(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META,
                                event_filter={"EVT_1", "EVT_2"}))
    assert {event for event, _ in results} == {"EVT_1", "EVT_2"}


def test_entry_shape_includes_parsed_labels_meta_and_latency():
    ph = prompt_hash(VOCAB, "audio")
    _, entry = next(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                 fake_generate, VOCAB, BACKEND_META,
                                 event_filter={"EVT_1"}))
    assert entry["labels"] == [{"word": "angry", "confidence": 0.9}]
    assert entry["parse_ok"] is True
    assert entry["model_id"] == "fake/model"
    assert entry["quant"] == "bf16"
    assert entry["temperature"] == 0.0
    assert entry["max_new_tokens"] == 192
    assert "latency_s" in entry and entry["latency_s"] >= 0
    assert "timestamp" in entry


def test_unparseable_response_still_yields_entry_with_parse_ok_false():
    ph = prompt_hash(VOCAB, "audio")
    _, entry = next(iter_labels(CATALOG, {}, "qwen2audio", "audio", ph,
                                 lambda wav, p: "not json at all",
                                 VOCAB, BACKEND_META, event_filter={"EVT_1"}))
    assert entry["parse_ok"] is False
    assert entry["labels"] == []


def test_audio_text_mode_skips_clip_with_no_transcript_instead_of_crashing():
    # Some catalog clips have an empty texts list (found live: 19/5188, mostly _unattributed
    # but a few named-speaker clips too) - audio+text mode has nothing to put in the prompt for
    # these, so it must skip them rather than IndexError on clip["texts"][0].
    catalog = dict(CATALOG, EVT_NO_TEXT={"speaker": "Abelard", "wav": "wav/Abelard/EVT_NO_TEXT.wav",
                                          "texts": []})
    ph = prompt_hash(VOCAB, "audio+text")
    results = list(iter_labels(catalog, {}, "qwen2audio", "audio+text", ph,
                                fake_generate, VOCAB, BACKEND_META,
                                event_filter={"EVT_NO_TEXT"}))
    assert results == []


def test_audio_only_mode_still_labels_a_clip_with_no_transcript():
    catalog = dict(CATALOG, EVT_NO_TEXT={"speaker": "Abelard", "wav": "wav/Abelard/EVT_NO_TEXT.wav",
                                          "texts": []})
    ph = prompt_hash(VOCAB, "audio")
    results = list(iter_labels(catalog, {}, "qwen2audio", "audio", ph,
                                fake_generate, VOCAB, BACKEND_META,
                                event_filter={"EVT_NO_TEXT"}))
    assert {event for event, _ in results} == {"EVT_NO_TEXT"}
