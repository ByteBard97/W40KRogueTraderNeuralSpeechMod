import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("librosa")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chorus  # noqa: E402

SR = 24000


def syllables(starts, dur=0.12, f=220.0, total=1.6):
    """Tone bursts at the given start times: a stand-in for words at known positions."""
    t = np.arange(int(total * SR)) / SR
    y = np.zeros_like(t)
    for s in starts:
        m = (t >= s) & (t < s + dur)
        y[m] = np.sin(2 * np.pi * f * t[m]) * np.hanning(m.sum())
    return y.astype(np.float32)


def onsets(y, thresh=0.2):
    """Start times of the bursts, from a smoothed envelope (a raw sine crosses any threshold many times)."""
    env = np.convolve(np.abs(y), np.ones(int(0.01 * SR)) / int(0.01 * SR), mode="same")
    on = env > thresh * env.max()
    return [i / SR for i in range(1, len(on)) if on[i] and not on[i - 1]]


def centroids(y, starts, width=0.2):
    """Energy-weighted centre time of the burst that starts near each of `starts`."""
    out = []
    for s in starts:
        a, b = int((s - 0.04) * SR), int((s + width) * SR)
        e = y[a:b] ** 2
        out.append((a + (np.arange(len(e)) * e).sum() / e.sum()) / SR)
    return out


def test_align_moves_late_words_onto_the_reference_timeline():
    ref = syllables([0.2, 0.6, 1.0])
    take = syllables([0.2, 0.68, 1.12], f=330.0, total=1.6)        # same words, a different pace
    y, d = chorus.align(ref, take, SR)
    want = centroids(ref, [0.2, 0.6, 1.0])
    before = centroids(take, [0.2, 0.68, 1.12])
    got = centroids(y, [0.2, 0.6, 1.0])
    assert all(abs(g - w) < 0.07 for g, w in zip(got, want)), (got, want)
    assert sum(abs(g - w) for g, w in zip(got, want)) < 0.6 * sum(abs(b - w) for b, w in zip(before, want))   # clearly closer than before
    assert d["stretch_max"] <= 1.26


def test_mix_returns_the_reference_length_and_stays_in_range():
    takes = [syllables([0.2, 0.6, 1.0], f=f, total=1.6 + 0.05 * i) for i, f in enumerate((200, 260, 330))]
    out, info = chorus.mix(takes, SR)
    assert len(info) == 3 and sum(i["reference"] for i in info) == 1
    assert out.dtype == np.float32 and np.max(np.abs(out)) <= 1.0 and len(out) > 0.8 * SR
