"""Behaviour tests for the stereo blocks (auto pan, stereo chorus, stereo phaser, bass spread), rendered through DawDreamer."""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402

CODE = (HERE / "faust/chain.dsp").read_text(encoding="utf-8")
SR = 24000


def run2(x, params):
    return dd_render.render(CODE, x.astype(np.float32), SR, params, 0.0, stereo=True)


def noise(seconds=6, seed=0):
    return (np.random.default_rng(seed).standard_normal(SR * seconds) * 0.1).astype(np.float32)


def tone(f, seconds=4.0, amp=0.3):
    n = np.arange(int(SR * seconds))
    return (amp * np.sin(2 * np.pi * f * n / SR)).astype(np.float32)


def band(y, lo, hi):
    return sosfilt(butter(4, [lo, hi], "bandpass", fs=SR, output="sos"), y)


def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def test_with_every_stereo_block_off_both_channels_are_the_same_signal():
    y = run2(noise(), {})
    assert y.shape[0] == 2 and np.array_equal(y[0], y[1])


def test_auto_pan_swings_the_balance_at_the_set_rate_and_is_unity_at_the_centre():
    y = run2(tone(500, 8.0), {"Auto_pan_depth_0_off": 1, "Auto_pan_rate_Hz": 1.0})
    h = SR // 50
    el = np.sqrt((y[0][: len(y[0]) // h * h].reshape(-1, h) ** 2).mean(1)) + 1e-6
    er = np.sqrt((y[1][: len(y[1]) // h * h].reshape(-1, h) ** 2).mean(1)) + 1e-6
    ild = 20 * np.log10(el / er)[50:]
    assert ild.max() > 15 and ild.min() < -15                             # swings (nearly) from one side to the other
    f = np.fft.rfftfreq(len(ild), 0.02)
    assert abs(f[np.argmax(np.abs(np.fft.rfft(ild - ild.mean())))] - 1.0) < 0.2        # at the set 1 Hz
    centre = run2(tone(500, 2.0), {"Auto_pan_depth_0_off": 0.001, "Auto_pan_rate_Hz": 0.05})
    assert abs(np.sqrt(np.mean(centre[0][SR:] ** 2)) / np.sqrt(np.mean(tone(500, 2.0)[SR:] ** 2)) - 1) < 0.02


def test_stereo_chorus_decorrelates_the_channels_only_when_on_and_when_the_right_side_is_offset():
    x = noise()
    off = run2(x, {"Stereo_chorus_mix_0_off": 0})
    assert corr(off[0], off[1]) > 0.9999
    on = run2(x, {"Stereo_chorus_mix_0_off": 1, "Stereo_chorus_depth_ms": 4, "Stereo_chorus_right_offset_deg": 180})
    assert corr(on[0][SR:], on[1][SR:]) < 0.9
    same = run2(x, {"Stereo_chorus_mix_0_off": 1, "Stereo_chorus_depth_ms": 4, "Stereo_chorus_right_offset_deg": 0})
    assert corr(same[0][SR:], same[1][SR:]) > 0.9999                         # no offset: both sides move together


def test_stereo_phaser_moves_the_two_sides_apart_with_an_offset_and_together_without():
    x = noise()
    p = {"Stereo_phaser_mix_0_off": 1, "Stereo_phaser_rate_Hz": 0.7, "Stereo_phaser_feedback": 0.5, "Stereo_phaser_stages_2_4_6_8": 6}
    apart = run2(x, {**p, "Stereo_phaser_right_offset_deg": 180})
    assert corr(apart[0][SR:], apart[1][SR:]) < 0.9
    together = run2(x, {**p, "Stereo_phaser_right_offset_deg": 0})
    assert corr(together[0][SR:], together[1][SR:]) > 0.9999
    assert abs(np.sqrt(np.mean(apart[0][SR:] ** 2)) / np.sqrt(np.mean(x[SR:] ** 2)) - 1) < 0.5     # a phaser is not a gain change


def test_bass_spread_decorrelates_the_lows_and_leaves_the_highs_coherent():
    x = noise(8)
    y = run2(x, {"Bass_spread_mix_0_off": 1, "Bass_spread_crossover_Hz": 300, "Bass_spread_delay_ms": 5, "Bass_spread_motion_depth": 0.8, "Bass_spread_motion_rate_Hz": 1.0})
    lows = (band(y[0], 100, 250)[SR:], band(y[1], 100, 250)[SR:])
    highs = (band(y[0], 1500, 5000)[SR:], band(y[1], 1500, 5000)[SR:])
    assert corr(*lows) < 0.8
    assert corr(*highs) > 0.98
    mono = np.sqrt(np.mean(y[0][SR:] ** 2) / np.mean(x[SR:] ** 2))
    assert 0.7 < mono < 1.3                                                  # the level of the voice is kept
