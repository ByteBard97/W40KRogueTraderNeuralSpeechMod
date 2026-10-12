import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# the module imports numpy/soundfile at the top; skip where they are missing
import pytest  # noqa: E402

pytest.importorskip("soundfile")
from real_vo_snippets import locate  # noqa: E402


def chunks(*ws):
    return [{"text": w, "timestamp": (i * 0.5, i * 0.5 + 0.4)} for i, w in enumerate(ws)]


def test_locates_by_position_even_when_whisper_misspells_the_name():
    span = locate("muaran", "Some like Muaran lay the blame", chunks("Some", "like", "Muaren", "lay", "the", "blame"))
    assert span == (1.0, 1.4)


def test_locates_multiword_term():
    span = locate("von valancius", "The von Valancius dynasty fell", chunks("The", "von", "valancius", "dynasty", "fell"))
    assert span == (0.5, 1.4)


def test_returns_none_when_term_is_not_in_the_text():
    assert locate("xenos", "Nothing here", chunks("Nothing", "here")) is None
