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


# ---- stereo ----
CHAIN = (Path(__file__).resolve().parents[1] / "faust/chain.dsp").read_text(encoding="utf-8")


def speechlike(sr=24000, seconds=2.0, seed=1):
    return (np.random.default_rng(seed).laplace(0, 0.05, int(sr * seconds))).astype(np.float32)


def test_a_preset_without_stereo_blocks_still_gives_a_mono_clip():
    x = speechlike()
    y = batch.process_clip(x, 24000, [{"dsp": "chain.dsp", "params": {"Ring_Hz": 40, "Ring_mix": 0.3}}], {"chain.dsp": CHAIN})
    assert y.ndim == 1


def test_a_preset_with_a_stereo_block_gives_two_channels_that_differ_and_match_the_loudness_of_the_raw_clip():
    x = speechlike()
    y = batch.process_clip(x, 24000, [{"dsp": "chain.dsp", "params": {"Stereo_chorus_mix_0_off": 1, "Stereo_chorus_depth_ms": 4}}], {"chain.dsp": CHAIN})
    assert y.shape[0] == 2 and np.abs(y[0] - y[1]).max() > 0.01
    stereo_rms = batch.active_rms(np.sqrt((y[0] ** 2 + y[1] ** 2) / 2), 24000)
    assert abs(stereo_rms / batch.active_rms(x, 24000) - 1) < 0.03                      # same loudness as the raw clip, both channels together
    assert np.abs(y).max() <= batch.PEAK_CEILING + 1e-4


def test_limiter_and_tail_trim_work_on_both_channels():
    sr = 24000
    y = np.zeros((2, sr), dtype=np.float32)
    y[0, 1000], y[1, 3000] = 1.5, 0.2
    out = batch.limit_peaks(y, sr)
    assert np.abs(out).max() <= batch.PEAK_CEILING + 1e-4 and abs(out[1, 3000]) < 0.2 + 1e-6 and abs(out[1, 3000]) > 0.05      # only the peak side dips
    z = np.zeros((2, sr), dtype=np.float32)
    z[1, 2000] = 0.5
    assert batch.trim_tail(z, sr).shape[1] < sr // 2                                     # the quiet end goes whichever channel carried the sound


# ---- graph presets: keys carry a node prefix (n3_Echo_mix), the program is a saved .dsp ----
def test_tail_seconds_finds_time_effects_under_node_prefixes():
    assert batch.tail_seconds({"n3_Echo_mix": 0.5, "n3_Echo_ms": 100}) > 0.5
    assert batch.tail_seconds({"n4_Reverb_mix": 0.3, "n4_Reverb_size": 0.8}) > 1.5
    assert batch.tail_seconds({"n5_Static_level_dB_60_off": -20, "n5_Static_tail_ms": 500}) > 0.5
    assert batch.tail_seconds({"n3_Echo_mix": 0.5, "n3_Echo_ms": 0}) == 0                   # an echo with no delay has no tail
    assert batch.tail_seconds({"n3_Echo_mix": 0.5, "n4_Echo_ms": 100}) == 0                 # mix of one echo and delay of another do not combine
    assert batch.tail_seconds({"n3_Ring_Hz": 40, "n3_Ring_mix": 0.3}) == 0


def test_tail_seconds_takes_the_longest_of_several_nodes():
    one = batch.tail_seconds({"n2_Echo_mix": 0.5, "n2_Echo_ms": 50})
    both = batch.tail_seconds({"n2_Echo_mix": 0.5, "n2_Echo_ms": 50, "n7_Echo_mix": 0.5, "n7_Echo_ms": 200})
    assert both > one and both <= batch.MAX_TAIL_S


def test_a_saved_graph_program_renders_with_keys_by_node_and_is_mono_when_the_sides_match():
    code = 'import("stdfaust.lib");\nprocess = vgroup("fx", _ <: vgroup("n1", *(hslider("Gain", 1, 0, 2, 0.01))), vgroup("n2", *(hslider("Gain", 1, 0, 2, 0.01))));\n'
    x = speechlike()
    same = batch.process_clip(x, 24000, [{"dsp": "presets/g.dsp", "params": {"n1_Gain": 0.5, "n2_Gain": 0.5}}], {"presets/g.dsp": code})
    assert same.ndim == 1                                                                   # left == right: stays mono
    differ = batch.process_clip(x, 24000, [{"dsp": "presets/g.dsp", "params": {"n1_Gain": 1.0, "n2_Gain": 0.25}}], {"presets/g.dsp": code})
    assert differ.shape[0] == 2 and np.abs(differ[0]).max() > 3 * np.abs(differ[1]).max()   # each instance honours its own gain
