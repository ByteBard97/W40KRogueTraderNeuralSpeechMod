"""Split a dialogue cue into ordered speech and narration segments.

The game marks narration with {n}...{/n} (the italic brown text in the dialog window); everything outside
those tags is the character speaking. Rendering each segment with its own voice and stitching them replaces
the old behaviour of speaking only the quoted part.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from build_test_set import NARR_SEG, narration_only, speech_only  # noqa: E402
from clean_text import clean_for_tts  # noqa: E402
from jobs import decode_binary  # noqa: E402

SPEECH, NARRATION = "speech", "narration"


def _spoken(kind: str, raw: str) -> str:
    cleaned = speech_only(raw) if kind == SPEECH else narration_only(raw)
    return clean_for_tts(decode_binary(cleaned))


def segments(text: str) -> list[tuple[str, str]]:
    """[(kind, spoken text)] in reading order. Segments with nothing to say are dropped; neighbours of the
    same kind (a tag that only wrapped markup) are merged."""
    out: list[tuple[str, str]] = []

    def add(kind: str, raw: str) -> None:
        spoken = _spoken(kind, raw)
        if not re.search(r"[A-Za-z]", spoken):
            return
        if out and out[-1][0] == kind:
            out[-1] = (kind, f"{out[-1][1]} {spoken}")
        else:
            out.append((kind, spoken))

    pos = 0
    for m in NARR_SEG.finditer(text):
        add(SPEECH, text[pos:m.start()])
        add(NARRATION, text[m.start():m.end()])
        pos = m.end()
    add(SPEECH, text[pos:])
    return out


def is_mixed(text: str) -> bool:
    kinds = {k for k, _ in segments(text)}
    return kinds == {SPEECH, NARRATION}
