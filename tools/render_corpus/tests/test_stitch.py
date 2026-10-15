import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from stitch import rms, stitch, trim_silence  # noqa: E402

SR = 24000


def tone(sec, amp=0.3, f=220.0):
    t = np.arange(int(sec * SR)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def test_trim_removes_edge_silence():
    x = np.concatenate([np.zeros(SR), tone(0.5), np.zeros(SR)])
    y = trim_silence(x, SR)
    assert 0.5 < len(y) / SR < 0.6


def test_stitch_length_is_parts_plus_pause():
    a, b = tone(1.0), tone(0.5)
    y = stitch([a, b], SR, pause_s=0.4)
    assert abs(len(y) / SR - (1.0 + 0.5 + 0.4)) < 0.15  # trim keep margins


def test_levels_are_matched_and_no_click_at_seam():
    y = stitch([tone(1.0, 0.1), tone(1.0, 0.4)], SR, pause_s=0.3)
    first, last = y[: SR // 2], y[-SR // 2:]
    assert abs(rms(first) - rms(last)) / rms(first) < 0.1
    assert np.max(np.abs(np.diff(y))) < 0.1   # a hard cut of a 0.3-amp tone would jump far more


def test_single_segment_and_empty():
    assert len(stitch([tone(0.5)], SR)) > 0
    assert len(stitch([], SR)) == 0


def test_never_clips():
    assert np.max(np.abs(stitch([tone(1.0, 0.99), tone(1.0, 0.99)], SR))) <= 1.0


def test_a_piece_uses_its_redo_take_when_its_own_is_not_usable():
    from takes import pick
    segs = {"p2": ("w2", {}), "p3@r1": ("w3", {}), "p5@r2": ("w5", {})}
    assert pick({"guid": "p2"}, segs) == "p2"                       # own take wins
    assert pick({"guid": "p3"}, segs) == "p3@r1"                    # a redo takes over
    assert pick({"guid": "p5"}, segs) == "p5@r2"                    # any of the redo numbers
    assert pick({"guid": "p4"}, segs) is None
