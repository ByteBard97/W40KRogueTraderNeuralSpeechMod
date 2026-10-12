import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from mixed import NARRATION, SPEECH, is_mixed, segments  # noqa: E402


def test_narration_then_speech():
    segs = segments('{n}Argenta\'s gaze darkens.{/n} "The warp, like a thief, steals our time."')
    assert [k for k, _ in segs] == [NARRATION, SPEECH]
    assert segs[0][1].startswith("Argenta")
    assert "warp" in segs[1][1] and '"' not in segs[1][1]


def test_speech_narration_speech():
    segs = segments('"Vladaym, Vladaym." {n}The woman sighs ostentatiously.{/n} "Where is my cargo?"')
    assert [k for k, _ in segs] == [SPEECH, NARRATION, SPEECH]


def test_pure_speech_and_pure_narration_are_not_mixed():
    assert not is_mixed('"Just talking here."')
    assert not is_mixed("{n}Only narration.{/n}")
    assert is_mixed('{n}He nods.{/n} "Fine."')


def test_empty_segments_are_dropped():
    assert [k for k, _ in segments('{n}...{/n} "Hello there, friend."')] == [SPEECH]
