import pytest

from context_window import (
    abelard_targets, canonical_chunk, chunk_ranges, dialogue_lines,
    target_indices, unlabeled_targets, validate_chunk_params,
)


def _line(text_key, speaker_name=None, text="hi", voiced=None, has_speaker_key=True):
    line = {"guid": text_key, "kind": "cue", "text_key": text_key, "text": text, "voiced": voiced}
    if has_speaker_key:
        line["speaker"] = {"name": speaker_name} if speaker_name else {}
    return line


def _structural(guid):
    """An answers_list-style node: no text, no text_key - real shape from conversations.enGB.json."""
    return {"guid": guid, "kind": "answers_list", "parent": None}


def test_abelard_targets_finds_unvoiced_abelard_lines_with_text():
    conv = {"lines": [
        _line("a", "Abelard", voiced=None),
        _line("b", "Abelard", voiced="SomeCatalogEvent_01"),
        _line("c", "Idira", voiced=None),
    ]}
    assert {t["text_key"] for t in abelard_targets(conv)} == {"a"}


def test_abelard_targets_skips_structural_nodes():
    conv = {"lines": [_line("a", "Abelard"), _structural("x")]}
    assert {t["text_key"] for t in abelard_targets(conv)} == {"a"}


def test_abelard_targets_skips_lines_with_no_speaker_key():
    # 23,689 real lines lack a `speaker` key entirely - must not crash on it.
    conv = {"lines": [_line("a", has_speaker_key=False)]}
    assert abelard_targets(conv) == []


def test_abelard_targets_dedupes_intra_conversation_duplicate_text_key():
    # LucidIdira_dialogue has exactly this shape in the real corpus: the same text_key
    # appearing twice for Abelard within one conversation. Without deduping here,
    # target_indices' dict-based lookup collapses both to one index while
    # validate_submission still iterates both as separate list entries, writing two
    # records with the same guid into one cache file's "lines" array.
    conv = {"lines": [_line("dup", "Abelard", text="first"), _line("dup", "Abelard", text="first")]}
    assert len(abelard_targets(conv)) == 1


def test_dialogue_lines_includes_all_speakers_excludes_structural():
    conv = {"lines": [_line("a", "Abelard"), _line("b", "Idira"), _structural("x")]}
    assert {l["text_key"] for l in dialogue_lines(conv)} == {"a", "b"}


def test_target_indices_maps_targets_to_dialogue_positions():
    dialogue = [_line("a", "Idira"), _line("b", "Abelard"), _line("c", "Idira")]
    targets = [_line("b", "Abelard")]
    assert target_indices(dialogue, targets) == [1]


def test_target_indices_uses_first_occurrence_for_a_duplicated_text_key():
    # Found during Task 1 review: a naive {key: i for i, line in enumerate(dialogue)}
    # dict comprehension keeps the LAST occurrence on a duplicate key, contradicting
    # abelard_targets' documented first-occurrence-wins contract for the exact real
    # corpus shape (LucidIdira_dialogue) this module's docstrings call out.
    dialogue = [_line("a", "Idira"), _line("dup", "Abelard", text="same"),
                _line("c", "Idira"), _line("dup", "Abelard", text="same")]
    targets = [_line("dup", "Abelard", text="same")]  # abelard_targets already deduped to one
    assert target_indices(dialogue, targets) == [1]


def test_chunk_ranges_whole_conversation_when_under_chunk_size():
    lines = [_line(str(i)) for i in range(10)]
    assert chunk_ranges(lines, target_indices=[3], chunk_size=50, overlap=10) == [(0, 10)]


def test_chunk_ranges_splits_long_conversation_with_overlap():
    lines = [_line(str(i)) for i in range(120)]
    # 10, 60, 100 each land in exactly one of the three raw ranges, so none get dropped
    ranges = chunk_ranges(lines, target_indices=[10, 60, 100], chunk_size=50, overlap=10)
    assert ranges == [(0, 50), (40, 90), (80, 120)]


def test_chunk_ranges_drops_ranges_with_no_target():
    lines = [_line(str(i)) for i in range(120)]
    ranges = chunk_ranges(lines, target_indices=[5], chunk_size=50, overlap=10)
    assert ranges == [(0, 50)]


def test_chunk_ranges_covers_every_line_index_with_no_gaps():
    # Regression guard for the empirical spec-review finding (0 of 572 real targets
    # dropped across all 219 conversations at the default 50/10 settings): if every
    # index is "a target", nothing may be silently excluded from every kept range.
    lines = [_line(str(i)) for i in range(150)]
    every_index = list(range(150))
    ranges = chunk_ranges(lines, target_indices=every_index, chunk_size=50, overlap=10)
    covered = set()
    for start, end in ranges:
        covered.update(range(start, end))
    assert covered == set(every_index)


def test_validate_chunk_params_rejects_overlap_at_or_above_chunk_size():
    with pytest.raises(ValueError):
        validate_chunk_params(chunk_size=50, overlap=50)
    with pytest.raises(ValueError):
        validate_chunk_params(chunk_size=50, overlap=60)


def test_validate_chunk_params_accepts_overlap_below_chunk_size():
    validate_chunk_params(chunk_size=50, overlap=10)  # must not raise


def test_canonical_chunk_single_range():
    assert canonical_chunk(5, [(0, 10)]) == 0


def test_canonical_chunk_picks_lower_index_in_overlap():
    ranges = [(0, 50), (40, 90)]
    assert canonical_chunk(45, ranges) == 0  # in both ranges - lower (earlier) wins


def test_canonical_chunk_raises_if_index_not_covered():
    with pytest.raises(ValueError):
        canonical_chunk(100, [(0, 50)])


def test_unlabeled_targets_excludes_already_labeled_keys():
    targets = [_line("a", "Abelard"), _line("b", "Abelard")]
    result = unlabeled_targets(targets, already_labeled_keys={"a"})
    assert {t["text_key"] for t in result} == {"b"}


def test_unlabeled_targets_empty_labeled_set_is_noop():
    targets = [_line("a", "Abelard")]
    assert unlabeled_targets(targets, already_labeled_keys=set()) == targets
