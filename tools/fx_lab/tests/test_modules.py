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


def peak_hz(y, lo=100, hi=11000):
    f, p = welch(y, SR, nperseg=16384)
    m = (f > lo) & (f < hi)
    return f[m][np.argmax(p[m])]


def level_db(y, hz, bw=15):
    f, p = welch(y, SR, nperseg=16384)
    return 10 * np.log10(p[(f > hz - bw) & (f < hz + bw)].sum() + 1e-18)


def test_frequency_shifter_moves_every_partial_the_same_number_of_hz_without_a_mirror_image():
    x = tone(1000, 2.0)
    up = run(x, {"Freq_shift_Hz_negative_shifts_down": 100, "Freq_shift_mix_0_off": 1})
    assert abs(peak_hz(up) - 1100) < 8
    assert level_db(up, 1100) - level_db(up, 900) > 25            # one sideband, not two
    down = run(x, {"Freq_shift_Hz_negative_shifts_down": -100, "Freq_shift_mix_0_off": 1})
    assert abs(peak_hz(down) - 900) < 8
    harmonic = tone(300, 2.0) + 0.5 * tone(600, 2.0) + 0.3 * tone(900, 2.0)
    y = run(harmonic, {"Freq_shift_Hz_negative_shifts_down": 40, "Freq_shift_mix_0_off": 1})
    for hz in (340, 640, 940):                                      # 300/600/900 -> 340/640/940: no longer a harmonic series
        assert level_db(y, hz) > level_db(y, hz - 40) + 20


def test_frequency_shifter_is_off_at_mix_zero_and_keeps_level_when_on():
    x = noise(4)
    y0 = run(x, {"Freq_shift_Hz_negative_shifts_down": 80})
    assert np.allclose(y0[SR // 4 :], x[SR // 4 :], atol=1e-4)           # the first 0.25 s holds the stomp switches' fade-in
    y = run(x, {"Freq_shift_Hz_negative_shifts_down": 0, "Freq_shift_mix_0_off": 1})
    assert abs(10 * np.log10(np.mean(y[SR:] ** 2) / np.mean(x[SR:] ** 2))) < 0.5      # an allpass pair: same loudness


def test_metal_bank_rings_at_bar_mode_frequencies_and_at_harmonics_when_inharmonicity_is_zero():
    x = noise(10)
    bar = run(x, {"Metal_mix_0_off": 1, "Metal_base_Hz": 300, "Metal_inharmonicity_0_harmonic_1_metal_bar": 1, "Metal_Q_ring_length": 40})
    assert response_db(bar, x, 300, 4) > 5 and response_db(bar, x, 826.8, 8) > 5 and response_db(bar, x, 1621, 15) > 5
    assert response_db(bar, x, 600, 8) < 1.5                         # 600 Hz is a harmonic, not a bar mode
    harm = run(x, {"Metal_mix_0_off": 1, "Metal_base_Hz": 300, "Metal_inharmonicity_0_harmonic_1_metal_bar": 0, "Metal_Q_ring_length": 40})
    assert response_db(harm, x, 600, 4) > 5 and response_db(harm, x, 900, 6) > 5 and response_db(harm, x, 826.8, 8) < 1.5


def test_metal_bank_leaves_the_voice_alone_when_off_and_stays_below_the_clip_level():
    x = noise()
    assert np.allclose(run(x, {"Metal_base_Hz": 500})[SR // 4 :], x[SR // 4 :], atol=1e-4)
    y = run(x, {"Metal_mix_0_off": 1, "Metal_Q_ring_length": 80})
    assert np.abs(y).max() < 0.95                                      # no clipping at the chain's +-1 ceiling even at the longest ring


def test_comb_puts_peaks_at_multiples_of_the_reciprocal_delay():
    x = noise(10)
    y = run(x, {"Comb_mix_0_off": 1, "Comb_delay_ms": 2.0, "Comb_feedback": 0.7})        # 2 ms -> peaks at 500, 1000, 1500 ... Hz
    for k in (1, 2, 3, 5):
        assert response_db(y, x, 500 * k, 12) - response_db(y, x, 500 * k - 250, 12) > 8
    odd = run(x, {"Comb_mix_0_off": 1, "Comb_delay_ms": 2.0, "Comb_feedback": -0.7})     # negative feedback: peaks at 250, 750, 1250 ...
    for k in (0, 1, 2):
        assert response_db(odd, x, 250 + 500 * k, 12) - response_db(odd, x, 500 * (k + 1), 12) > 8


def test_comb_is_transparent_when_off_and_keeps_the_overall_level_of_noise():
    x = noise()
    assert np.allclose(run(x, {"Comb_feedback": 0.8})[SR // 4 :], x[SR // 4 :], atol=1e-4)
    y = run(x, {"Comb_mix_0_off": 1, "Comb_delay_ms": 3, "Comb_feedback": 0.8})
    assert 0.8 < np.sqrt(np.mean(y[SR:] ** 2) / np.mean(x[SR:] ** 2)) < 1.25


def test_the_chain_passes_the_voice_through_unchanged_when_every_block_is_neutral():
    x = noise(4)
    y = run(x, {})
    assert np.max(np.abs(y[SR // 4 :] - x[SR // 4 :])) < 1e-4          # an old phase-rotating high shelf made this 100% different
