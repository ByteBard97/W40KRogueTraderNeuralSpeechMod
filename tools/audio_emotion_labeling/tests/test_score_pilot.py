from score_pilot import build_report, duplicate_base_lines

WORD_TO_TIER = {"angry": "Original", "commanding": "Original", "rueful": "Low-mid energy",
                 "somber": "Low energy"}

GROUND_TRUTH = {"EVT_1": "rueful", "EVT_2": "commanding"}

LABELS = {
    "EVT_1": {"qwen2audio": {"audio": {"ph1": {
        "labels": [{"word": "somber", "confidence": 0.8}, {"word": "rueful", "confidence": 0.3}],
        "notes": "", "parse_ok": True}}}},
    "EVT_2": {"qwen2audio": {"audio": {"ph1": {
        "labels": [{"word": "angry", "confidence": 0.9}],
        "notes": "", "parse_ok": True}}}},
}


def test_report_computes_top1_and_recall():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert report["n_scored"] == 2
    assert report["top1_exact"] == 0.0  # neither top-1 pick was the exact human word
    assert report["recall_at_2"] == 0.5  # EVT_1's rueful is recall@2, EVT_2's commanding never appears


def test_report_computes_best_of_set_similarity_mean():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    # EVT_1: max(sim(rueful,somber)=0.4, sim(rueful,rueful)=1.0) = 1.0
    # EVT_2: sim(commanding,angry) = 0.0 - both are real vocab.py words with a scoring-only
    # energy-tier override (see scoring.py's _LEGACY_ENERGY_OVERRIDE); they land two
    # ladder steps apart (Mid vs High), not the same tier this fixture's WORD_TO_TIER
    # naively assigns them both to ("Original") - the override takes precedence.
    assert report["graded_similarity_mean"] == (1.0 + 0.0) / 2


def test_report_disagreement_list_only_has_top1_mismatches():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert {d["event"] for d in report["disagreements"]} == {"EVT_1", "EVT_2"}


def test_report_skips_events_with_no_ground_truth():
    labels = dict(LABELS)
    labels["EVT_3"] = {"qwen2audio": {"audio": {"ph1": {
        "labels": [{"word": "angry", "confidence": 0.5}], "notes": "", "parse_ok": True}}}}
    report = build_report(GROUND_TRUTH, labels, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert report["n_scored"] == 2


def test_report_disagreements_carry_event_context_when_given():
    event_context = {
        "EVT_1": {"transcript": "Dreaming of feasting...", "text_llm_emotion": "sad"},
        "EVT_2": {"transcript": "Typical.", "text_llm_emotion": None},
    }
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1",
                           event_context=event_context)
    by_event = {d["event"]: d for d in report["disagreements"]}
    assert by_event["EVT_1"]["transcript"] == "Dreaming of feasting..."
    assert by_event["EVT_1"]["text_llm_emotion"] == "sad"
    assert by_event["EVT_2"]["text_llm_emotion"] is None


def test_report_disagreements_omit_context_fields_when_not_given():
    report = build_report(GROUND_TRUTH, LABELS, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert "transcript" not in report["disagreements"][0]


def test_duplicate_base_lines_groups_state_variant_siblings():
    ground_truth = {
        "PRL_Foo_04 [statevar=1]": "sad", "PRL_Foo_04 [statevar=2]": "sad",
        "PRL_Bar_01": "angry",
    }
    dupes = duplicate_base_lines(ground_truth)
    assert dupes == {"PRL_Foo_04": ["PRL_Foo_04 [statevar=1]", "PRL_Foo_04 [statevar=2]"]}


def test_report_tracks_parse_failure_rate_separately_from_wrong_answers():
    labels = dict(LABELS)
    labels["EVT_1"] = {"qwen2audio": {"audio": {"ph1": {
        "labels": [], "notes": "", "parse_ok": False, "raw_response": "not valid json"}}}}
    report = build_report(GROUND_TRUTH, labels, WORD_TO_TIER, "qwen2audio", "audio", "ph1")
    assert report["parse_failure_rate"] == 0.5  # EVT_1 failed, EVT_2 parsed fine
