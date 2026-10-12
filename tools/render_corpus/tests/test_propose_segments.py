import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from propose_segments import split_labelled  # noqa: E402
from segment_annotations import validate  # noqa: E402

SKEL = ('The cogitator is damaged. "Scout 1: WE\'RE RICH! Chaos take me! Lookout: Fly, for crying out loud, '
        'spit it out. Scout 1: I want a house on some planet. Lookout: Get back here."')


def test_splits_on_labels_and_validates():
    segs = split_labelled(SKEL)
    assert [s["speaker"] for s in segs] == ["narrator", "Scout 1", "Lookout", "Scout 1", "Lookout"]
    assert segs[0]["kind"] == "narration" and segs[1]["kind"] == "speech"
    assert validate(SKEL, {"segments": segs}) == []


def test_adjacent_lines_by_one_speaker_stay_separate_so_the_guard_can_check_them():
    segs = split_labelled('"Scout 1: Rich! Lookout: Fly. Lookout: Fly. You coming? Scout 1: Yes."')
    assert [s["speaker"] for s in segs] == ["Scout 1", "Lookout", "Lookout", "Scout 1"]


def test_data_labels_are_not_speakers():
    assert split_labelled('"Location: Footfall. Material: iron. Region: Expanse."') is None


def test_one_label_is_not_enough():
    assert split_labelled('"Lookout: Fly, are you there?"') is None


def test_newline_separated_labels_validate_against_the_cue():
    cue = '"Scout 1: Rich!\nLookout: Fly.\nLookout: Fly. You coming?\nScout 1: Yes."'
    segs = split_labelled(cue)
    assert validate(cue, {"segments": segs}) == []


def test_record_fields_are_not_speakers():
    assert split_labelled('"Koronus Expanse Location: Footfall. Valancius flagship Material: iron."') is None
    assert split_labelled('"PROCESS: Scan complete. STATUS: Ready."') is None
