from speaker_vocab import build_agreement_counts, event_agreement_words, select_vocab

VALID = {"angry", "somber", "commanding", "fear"}


def _entry(*words):
    return {"labels": [{"word": w, "confidence": 0.8} for w in words]}


def test_event_agreement_words_intersects_top_k_across_modes():
    audio = _entry("angry", "commanding", "fear")
    text = _entry("commanding", "angry", "somber")
    assert event_agreement_words(audio, text, VALID, top_k=2) == {"angry", "commanding"}


def test_event_agreement_words_excludes_word_only_in_one_mode():
    audio = _entry("angry", "fear")
    text = _entry("somber", "commanding")
    assert event_agreement_words(audio, text, VALID, top_k=2) == set()


def test_event_agreement_words_filters_non_vocabulary_words():
    # 'heresy' isn't a real emotion word (parsing artifact / transcript echo) - must be
    # dropped even though it agrees across both modes.
    audio = _entry("angry", "heresy")
    text = _entry("heresy", "angry")
    assert event_agreement_words(audio, text, VALID, top_k=2) == {"angry"}


def test_event_agreement_words_handles_missing_entry():
    audio = _entry("angry")
    assert event_agreement_words(audio, None, VALID, top_k=2) == set()
    assert event_agreement_words(None, None, VALID, top_k=2) == set()


def test_event_agreement_words_respects_top_k_cutoff():
    audio = _entry("angry", "commanding", "fear")
    text = _entry("fear", "somber", "angry")  # 'fear' at rank 1, but 'angry' at rank 3
    assert event_agreement_words(audio, text, VALID, top_k=1) == set()
    assert event_agreement_words(audio, text, VALID, top_k=3) == {"angry", "fear"}


def test_build_agreement_counts_aggregates_across_events():
    speaker_labels = {
        "ev1": {"audio": _entry("angry", "commanding"), "audio+text": _entry("angry", "fear")},
        "ev2": {"audio": _entry("angry", "somber"), "audio+text": _entry("somber", "angry")},
        "ev3": {"audio": _entry("fear"), "audio+text": _entry("commanding")},
    }
    counts, examples = build_agreement_counts(speaker_labels, VALID, top_k=2)
    assert counts["angry"] == 2
    assert counts["somber"] == 1
    assert "commanding" not in counts
    assert examples["angry"] == ["ev1", "ev2"]


def test_select_vocab_filters_by_threshold_and_sorts_by_count_then_alpha():
    from collections import Counter
    counts = Counter({"angry": 5, "somber": 2, "fear": 5, "commanding": 1})
    assert select_vocab(counts, threshold=2) == ["angry", "fear", "somber"]
    assert select_vocab(counts, threshold=6) == []
