import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from plan import is_unquoted_narration  # noqa: E402


def test_unquoted_line_from_unnamed_speaker_is_narration():
    assert is_unquoted_narration("default_speaker", "Entry M-001.87.23. 30 chronometer turns since the incident.")
    assert is_unquoted_narration("unit", "Placeholder")


def test_quoted_line_or_named_speaker_is_not():
    assert not is_unquoted_narration("default_speaker", 'The man says "Move along."')
    assert not is_unquoted_narration("npc", "Move along.")
    assert not is_unquoted_narration(None, "Move along.")
