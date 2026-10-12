"""Pure-function tests for batch.py (run: tools/fx_lab/.venv-fx/bin/python -m pytest tools/fx_lab/tests)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import batch  # noqa: E402

SR = 24000


def tone(seconds=1.0, amp=0.5, f=220):
    n = np.arange(int(SR * seconds))
    return (amp * np.sin(2 * np.pi * f * n / SR)).astype(np.float32)


def test_tail_seconds_zero_without_time_effects():
    assert batch.tail_seconds({"Drive": 0.5}) == 0


def test_tail_seconds_grows_with_echo_and_reverb_and_is_capped():
    assert batch.tail_seconds({"Echo_ms": 100, "Echo_mix": 0.3}) == 0.8
    assert batch.tail_seconds({"Reverb_mix": 0.2, "Reverb_size": 0.9}) > 1.5
    assert batch.tail_seconds({"Echo_ms": 500, "Echo_mix": 1}) == batch.MAX_TAIL_S


def test_trim_tail_removes_trailing_silence_but_keeps_a_margin():
    x = np.concatenate([tone(0.5), np.zeros(SR * 2, dtype=np.float32)])
    y = batch.trim_tail(x, SR)
    assert abs(len(y) - (SR * 0.5 + SR * batch.KEEP_AFTER_S)) < 5


def test_match_loudness_hits_reference_and_respects_ceiling():
    ref = tone(1.0, 0.1)
    quiet = tone(1.0, 0.01)
    out = batch.match_loudness(quiet, ref, SR)
    assert abs(batch.active_rms(out, SR) - batch.active_rms(ref, SR)) < 0.005
    loud_ref = tone(1.0, 0.9)
    out2 = batch.match_loudness(tone(1.0, 0.05), loud_ref, SR)
    assert np.max(np.abs(out2)) <= batch.PEAK_CEILING + 1e-6


def test_limit_peaks_only_dips_around_the_peak():
    y = tone(1.0, 0.2)
    y[SR // 2] = 3.0
    out = batch.limit_peaks(y, SR)
    assert np.max(np.abs(out)) <= batch.PEAK_CEILING + 1e-6
    assert abs(np.abs(out[SR // 10]) - np.abs(y[SR // 10])) < 1e-6        # far from the peak: untouched


def test_active_rms_ignores_silence():
    x = np.concatenate([tone(0.5, 0.4), np.zeros(SR * 2, dtype=np.float32)])
    assert abs(batch.active_rms(x, SR) - 0.4 / np.sqrt(2)) < 0.02
