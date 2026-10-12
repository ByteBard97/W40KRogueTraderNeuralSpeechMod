"""Behaviour tests for the live Faust modules, rendered through DawDreamer (run: .venv-fx/bin/python -m pytest tools/fx_lab/tests).
The null test (null_test.py) separately checks that FaustWasm and DawDreamer agree."""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import welch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402

CODE = (HERE / "faust/chain.dsp").read_text(encoding="utf-8")
SR = 24000


def run(x, params, tail=0.0):
    return dd_render.render(CODE, x.astype(np.float32), SR, params, tail)


def noise(seconds=8, seed=0):
    return (np.random.default_rng(seed).standard_normal(SR * seconds) * 0.1).astype(np.float32)


def tone(f, seconds=2.0, amp=0.3):
    n = np.arange(int(SR * seconds))
    return (amp * np.sin(2 * np.pi * f * n / SR)).astype(np.float32)


def response_db(y, x, f0, bw=100):
    f, py = welch(y, SR, nperseg=8192)
    _, px = welch(x, SR, nperseg=8192)
    m = (f > f0 - bw) & (f < f0 + bw)
    return 10 * np.log10(py[m].mean() / px[m].mean())


def test_eq_boosts_where_set_and_leaves_the_rest():
    x = noise()
    y = run(x, {"EQ_mid_freq_Hz": 1000, "EQ_mid_gain_dB": 12, "EQ_mid_Q": 1})
    assert 10 < response_db(y, x, 1000) < 13
    assert abs(response_db(y, x, 5000, 300)) < 1.0
    assert abs(response_db(y, x, 150, 30)) < 1.5


def test_eq_high_shelf_and_cut():
    x = noise()
    y = run(x, {"EQ_shelf_freq_Hz": 3000, "EQ_shelf_gain_dB": 6, "EQ_low_freq_Hz": 300, "EQ_low_gain_dB": -9})
    assert 4 < response_db(y, x, 8000, 500) < 7
    assert response_db(y, x, 300, 20) < -6


def test_harmonizer_adds_an_octave_below():
    x = tone(400, 2.0)
    base = run(x, {})
    y = run(x, {"Harmonizer_voice_1_semitones": -12, "Harmonizer_voice_1_level": 0.6})
    f, p = welch(y, SR, nperseg=8192)
    f0, p0 = welch(base, SR, nperseg=8192)
    at = lambda f_, P, hz: P[(f_ > hz - 15) & (f_ < hz + 15)].sum()
    assert at(f, p, 200) > 20 * at(f0, p0, 200)        # energy appears at 200 Hz
    assert at(f, p, 400) > 0.5 * at(f0, p0, 400)       # the dry voice is still there


def test_resonator_adds_peaks_at_the_set_frequencies():
    x = noise()
    y = run(x, {"Resonator_mix_0_off": 1, "Resonator_freq_1_Hz": 700, "Resonator_Q": 15})
    assert response_db(y, x, 700, 30) > 3
    assert abs(response_db(y, x, 1300, 100)) < 3


def test_wow_flutter_modulates_pitch_by_about_the_requested_cents():
    x = tone(1000, 4.0)
    y = run(x, {"Wow_cents": 40, "Wow_rate_Hz": 1.0})
    from scipy.signal import hilbert
    ph = np.unwrap(np.angle(hilbert(y[SR : SR * 4])))
    inst = np.convolve(np.diff(ph), np.ones(240) / 240, "same") * SR / (2 * np.pi)   # 10 ms smoothed instantaneous frequency
    cents = 1200 * np.log2(inst[2400:-2400] / 1000)
    assert 25 < (np.percentile(cents, 97) - np.percentile(cents, 3)) / 2 < 55   # about +-40 cents


def test_dropout_mutes_about_the_expected_fraction():
    x = tone(300, 10.0)
    y = run(x, {"Dropout_amount_0_off": 1.0, "Dropout_rate_per_s": 5, "Dropout_length_ms": 100})
    muted = np.mean(np.abs(y[SR:]) < 0.003)
    assert 0.35 < muted < 0.65                           # 100 ms muted out of every 200 ms
    y0 = run(x, {"Dropout_amount_0_off": 0.0})
    assert np.mean(np.abs(y0[SR:]) < 0.003) < 0.05


def test_dropout_is_the_same_each_run():
    x = tone(300, 4.0)
    p = {"Dropout_amount_0_off": 0.5, "Dropout_rate_per_s": 8, "Dropout_length_ms": 60}
    assert np.array_equal(run(x, p), run(x, p))
