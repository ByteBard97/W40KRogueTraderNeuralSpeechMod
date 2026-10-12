import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from segment_annotations import validate  # noqa: E402

CUE = '"Scout 1: WE\'RE RICH! Lookout: Fly, spit it out. What have you found?"'


def seg(speaker, text, kind="speech"):
    return {"speaker": speaker, "kind": kind, "text": text}


def test_labelled_cue_is_valid_when_labels_are_the_only_leftover():
    entry = {"segments": [seg("Scout 1", "WE'RE RICH!"), seg("Lookout", "Fly, spit it out. What have you found?")]}
    assert validate(CUE, entry) == []


def test_text_not_covered_is_rejected():
    entry = {"segments": [seg("Scout 1", "WE'RE RICH!"), seg("Lookout", "What have you found?")]}
    errs = validate(CUE, entry)
    assert any("not covered" in e for e in errs)


def test_out_of_order_segments_are_rejected():
    entry = {"segments": [seg("Lookout", "What have you found?"), seg("Scout 1", "WE'RE RICH!")]}
    assert validate(CUE, entry)


def test_single_segment_and_bad_kind_are_rejected():
    assert validate(CUE, {"segments": [seg("Scout 1", "WE'RE RICH!")]})
    assert validate(CUE, {"segments": [seg("a", "WE'RE RICH!", "shout"), seg("b", "Fly")]})


def test_label_word_dropped_mid_gap_is_rejected():
    cue = '"Listen: we go. Lookout: Fine."'
    entry = {"segments": [seg("Ava", "we go."), seg("Lookout", "Fine.")]}
    assert validate(cue, entry)


REAL = ('{n}The {g|Encyclopedia:Cogitator}cogitator{/g} is damaged.{/n}\n"Scout 1: RICH! Screw {g|Encyclopedia:Footfall}Footfall{/g}!\n'
        'Lookout: Yeah, because with our record, Calixis is the place to go."')


def test_real_game_markup_with_glossary_links():
    entry = {"segments": [seg("narrator", "The cogitator is damaged.", "narration"), seg("Scout 1", "RICH! Screw Footfall!"),
                          seg("Lookout", "Yeah, because with our record, Calixis is the place to go.")]}
    assert validate(REAL, entry) == []


def test_n_tags_in_the_cue_are_ignored():
    cue = '{n}He grins.{/n} "Mine!" {n}She frowns.{/n}'
    entry = {"segments": [seg("narrator", "He grins.", "narration"), seg("Ava", "Mine!"), seg("narrator", "She frowns.", "narration")]}
    assert validate(cue, entry) == []


def test_cue_with_no_speech_segment_is_rejected():
    cue = '{n}He grins.{/n} {n}She frowns.{/n}'
    entry = {"segments": [seg("narrator", "He grins.", "narration"), seg("narrator", "She frowns.", "narration")]}
    assert any("speech" in e for e in validate(cue, entry))
