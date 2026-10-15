"""Block library: every node_<id> in faust/blocks.lib against the chain_v1.dsp oracle, plus bypass, independence and catalog checks.

Run: tools/fx_lab/.venv-fx/bin/python -m pytest tools/fx_lab/tests
The oracle settings are v1 control keys (dd_render.short of the label); the block program takes the same values under the n1_ prefix.
Output is compared from 0.25 s on, because every stomp and slider fades in with si.smoo from zero.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402
import null_test  # noqa: E402

SR = null_test.SR
LIB = (HERE / "faust/blocks.lib").read_text(encoding="utf-8")
V1 = (HERE / "faust/chain_v1.dsp").read_text(encoding="utf-8")
CATALOG = json.loads((HERE / "faust/catalog.json").read_text(encoding="utf-8"))
BLOCKS = {b["id"]: b for b in CATALOG["blocks"]}
SKIP = int(0.25 * SR)
TAIL = 0.5

# Settings (v1 keys) that make each effect audible. Mix, output and input have their own tests below.
CASES = {
    "highpass": {"Highpass_Hz_0_off": 300},
    "lowpass": {"Lowpass_Hz_0_off": 3400},
    "deesser": {"De_ess_threshold_dB_0_off": -30, "De_ess_frequency_Hz": 3000},
    "eq": {"EQ_mid_gain_dB": 9, "EQ_low_gain_dB": -6, "EQ_shelf_gain_dB": 6},
    "lowshelf": {"Low_shelf_dB_200_Hz": 6},
    "compressor": {"Compressor_ratio_1_off": 8, "Compressor_threshold_dB": -30, "Compressor_makeup_dB": 6},
    "pitch": {"Pitch_semitones": -3},
    "harmonizer": {"Harmonizer_voice_1_level": 0.6, "Harmonizer_voice_2_level": 0.4},
    "freqshift": {"Freq_shift_Hz_negative_shifts_down": 35, "Freq_shift_mix_0_off": 1},
    "vocoder": {"Vocoder_mix_0_off": 1, "Vocoder_carrier_noise": 0.2},
    "wowflutter": {"Wow_cents": 20, "Flutter_cents": 10},
    "resonator": {"Resonator_mix_0_off": 0.8},
    "metal": {"Metal_mix_0_off": 0.8, "Metal_base_Hz": 260, "Metal_Q_ring_length": 40},
    "comb": {"Comb_mix_0_off": 0.8, "Comb_delay_ms": 2.5, "Comb_feedback": 0.6},
    "ringmod": {"Ring_Hz": 40, "Ring_mix": 0.6},
    "drive": {"Drive": 0.4},
    "bitcrush": {"Crush_bits_16_off": 6, "Crush_hold_samples": 3},
    "tremolo": {"Tremolo_Hz": 5, "Tremolo_depth": 0.7},
    "chorus": {"Chorus_mix_0_off": 0.7, "Chorus_depth_ms": 4},
    "phaser": {"Phaser_mix_0_off": 0.9, "Phaser_rate_Hz": 0.8, "Phaser_feedback": 0.5, "Phaser_stages_2_4_6_8": 6},
    "echo": {"Echo_ms": 90, "Echo_feedback": 0.4, "Echo_mix": 0.5},
    "reverb": {"Reverb_mix": 0.3},
    "static": {"Static_level_dB_60_off": -20},
    "dropout": {"Dropout_amount_0_off": 0.6},
    "autopan": {"Auto_pan_depth_0_off": 0.9, "Auto_pan_rate_Hz": 1.3},
    "stereochorus": {"Stereo_chorus_mix_0_off": 0.7, "Stereo_chorus_depth_ms": 4, "Stereo_chorus_right_offset_deg": 120},
    "stereophaser": {"Stereo_phaser_mix_0_off": 0.9, "Stereo_phaser_rate_Hz": 0.8, "Stereo_phaser_feedback": 0.5, "Stereo_phaser_stages_2_4_6_8": 6},
    "bassspread": {"Bass_spread_mix_0_off": 1, "Bass_spread_delay_ms": 6, "Bass_spread_motion_depth": 0.7},
    "output": {"Output_dB": 6, "Limiter_threshold_dB_0_off": -12},
}
# Tolerance (min correlation, max relative RMS). The blocks are the same Faust expressions as the oracle, so the default is tight.
# Bit crush floors the signal to 6 bits: a float32 rounding difference of one ulp between the two compiles occasionally lands on the other side
# of a quantisation step, a one-step (0.032) error on a few samples. Everything else is identical, so only this block gets a looser RMS bound.
TOL = {"bitcrush": (0.9999, 5e-3)}
DEFAULT_TOL = (0.9999, 1e-3)
EFFECTS = [i for i, b in BLOCKS.items() if b["kind"] == "effect"]


def signal():
    x = null_test.test_signal()
    burst = np.zeros_like(x)
    a = int(1.2 * SR)
    burst[a:a + int(0.2 * SR)] = (np.random.default_rng(1).standard_normal(int(0.2 * SR)) * 0.1).astype(np.float32)
    return (x + burst).astype(np.float32)


X = signal()


def program(block_id):
    b = BLOCKS[block_id]
    return f'{LIB}\nprocess = vgroup("fx", _ <: si.bus({2 * b["inputs"]}) : vgroup("n1", {b["node"]}));\n'


def prefixed(params):
    return {f"n1_{k}": v for k, v in params.items()}


def run_block(block_id, params):
    return dd_render.render(program(block_id), X, SR, prefixed(params), TAIL, stereo=True)


def run_oracle(params):
    return dd_render.render(V1, X, SR, params, TAIL, stereo=True)


def block_text(block_id):
    m = re.search(rf"^node_{block_id} = .*?^\}};", LIB, re.S | re.M)
    assert m, block_id
    return m.group(0)


def agree(a, b, tol=DEFAULT_TOL):
    r = null_test.compare(a[:, SKIP:], b[:, SKIP:])
    assert r["corr"] >= tol[0] and r["rel_rms"] <= tol[1], r


@pytest.mark.parametrize("block_id", list(CASES))
def test_block_matches_the_oracle_chain(block_id):
    params = CASES[block_id]
    # The oracle ends in the hard clip (the output block); a lone effect block has none, so clip the block's result the same way.
    agree(np.clip(run_block(block_id, params), -1, 1), run_oracle(params), TOL.get(block_id, DEFAULT_TOL))


@pytest.mark.parametrize("block_id", EFFECTS)
def test_off_is_transparent(block_id):
    params = dict(CASES[block_id])
    params[dd_render.short(BLOCKS[block_id]["stomp"])] = 0
    y = run_block(block_id, params)
    n = len(X)
    for ch in range(2):
        r = null_test.compare(X[SKIP:n], y[ch, SKIP:n])
        assert r["rel_rms"] < 1e-3, (ch, r)


@pytest.mark.parametrize("block_id", EFFECTS)
def test_two_instances_have_independent_controls(block_id):
    code = (f'{LIB}\nprocess = vgroup("fx", _ <: (_,_,_,_) : (vgroup("n1", {BLOCKS[block_id]["node"]}), vgroup("n2", {BLOCKS[block_id]["node"]})));\n')
    keys = dd_render.list_params(code, SR)
    own = [c["label"] for c in BLOCKS[block_id]["controls"]]
    assert sorted(keys) == sorted([f"n{i}_{dd_render.short(label)}" for i in (1, 2) for label in own])
    y = dd_render.render(code, X, SR, prefixed(CASES[block_id]), TAIL, stereo=True)
    assert y.shape[0] == 4
    agree(y[:2], run_block(block_id, CASES[block_id]), (0.99999999, 1e-6))   # same code, same engine settings: bit-level equal
    agree(y[2:], run_block(block_id, {}), (0.99999999, 1e-6))


@pytest.mark.parametrize("block_id", [i for i in EFFECTS if not BLOCKS[i]["stereoNative"]])
def test_mono_block_channels_are_identical(block_id):
    y = run_block(block_id, CASES[block_id])
    assert np.array_equal(y[0], y[1])


@pytest.mark.parametrize("block_id", [i for i in BLOCKS if i != "input"])
def test_controls_collapse_to_one_set(block_id):
    """The par(i, 2, ...) copies of a mono block fold into one control each: the compiled count equals the widgets written in the block."""
    text = block_text(block_id)
    written = len(re.findall(r'\b(?:hslider|checkbox)\(', text))
    assert len(BLOCKS[block_id]["controls"]) == written
    labels = [c["label"] for c in BLOCKS[block_id]["controls"]]
    assert len(labels) == len(set(labels))


@pytest.mark.parametrize("block_id", [i for i in BLOCKS if i != "input"])
def test_compiles_in_both_runtimes(block_id, tmp_path):
    dsp = tmp_path / f"{block_id}.dsp"
    dsp.write_text(program(block_id), encoding="utf-8")
    x = X[:SR]
    yw = null_test.wasm_render(dsp, x, {}, 0.0)
    yd = dd_render.render(program(block_id), x, SR, {}, 0.0, stereo=True)
    assert yw.shape == (2, len(x)) and yd.shape == (2, len(x))
    assert np.isfinite(yw).all() and np.isfinite(yd).all()


def test_mix_nodes_sum_with_their_levels():
    levels = {"A": 0, "B": -6, "C": 3, "D": -12}
    for n in (2, 3, 4):
        names = list("ABCD")[:n]
        params = {f"Level_{c}_dB": levels[c] for c in names}
        y = run_block(f"mix{n}", params)
        gain = sum(10 ** (levels[c] / 20) for c in names)
        for ch in range(2):
            r = null_test.compare(X[SKIP:len(X)] * gain, y[ch, SKIP:len(X)])
            assert r["rel_rms"] < 1e-4, (n, ch, r)


def test_output_clips_and_keeps_the_exact_unclip_substring():
    y = run_block("output", {"Output_dB": 12})
    assert np.abs(y).max() <= 1.0
    assert LIB.count("max(-1) : min(1)") == 1 and block_text("output").count("max(-1) : min(1)") == 1   # batch.py unclip() replaces this text


def test_input_is_structural():
    b = BLOCKS["input"]
    assert (b["inputs"], b["outputs"], b["controls"], b["node"]) == (0, 1, [], None)


def test_lib_has_no_extra_imports():
    assert re.findall(r'^\s*(?:import|include)\(', LIB, re.M) == ['import(']
    assert LIB.count('import("stdfaust.lib");') == 1


def test_catalog_equals_a_fresh_rebuild():
    r = subprocess.run(["node", str(HERE / "build_catalog.mjs"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_catalog_control_has_numeric_init_min_max_and_step():
    """FaustWasm gives checkboxes no init/min/max/step; the catalog must still carry 1/0/1/1 so params and the UI never see null."""
    cat = json.loads((Path(__file__).resolve().parents[1] / "faust/catalog.json").read_text())
    for b in cat["blocks"]:
        for c in b["controls"]:
            assert all(isinstance(c[k], (int, float)) for k in ("init", "min", "max", "step")), (b["id"], c)
            if c["type"] == "checkbox":
                assert (c["init"], c["min"], c["max"], c["step"]) == (1, 0, 1, 1)
