"""Parameter addressing: a control's key is its full address with the root stripped, in both runtimes (DawDreamer and FaustWasm)."""
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402
import null_test  # noqa: E402

SR = 24000
BLOCK = 'blk(x) = x * hslider("Gain", 1, 0, 2, 0.01);\n'
# Generated programs wrap everything in one outer group. Without it, Faust makes a lone top-level group the root and drops it from the
# address ('/n1/Gain'), so there would be no root segment to strip.
TWO = f'import("stdfaust.lib");\n{BLOCK}process = vgroup("fx", _ <: vgroup("n1", blk), vgroup("n2", blk));\n'
ONE = f'import("stdfaust.lib");\n{BLOCK}process = vgroup("fx", _ <: vgroup("n1", blk), _);\n'
LONE_GROUP = f'import("stdfaust.lib");\n{BLOCK}process = _ <: vgroup("n1", blk), _;\n'     # what NOT to generate: the address loses its root
X = (np.random.default_rng(0).standard_normal(SR) * 0.1).astype(np.float32)


def wasm(tmp_path, code, params):
    p = tmp_path / "t.dsp"
    p.write_text(code)
    return null_test.wasm_render(p, X, params, 0.0)


def ratio(y, ch):
    return float(np.sqrt(np.mean(y[ch] ** 2) / np.mean(X ** 2)))


def test_two_blocks_with_the_same_label_get_separate_keys_in_dawdreamer():
    assert dd_render.list_params(TWO, SR) == ["n1_Gain", "n2_Gain"]
    y = dd_render.render(TWO, X, SR, {"n1_Gain": 1.5, "n2_Gain": 0.25}, stereo=True)
    assert abs(ratio(y, 0) - 1.5) < 0.01 and abs(ratio(y, 1) - 0.25) < 0.01


def test_two_blocks_with_the_same_label_get_separate_keys_in_faustwasm(tmp_path):
    y = wasm(tmp_path, TWO, {"n1_Gain": 1.5, "n2_Gain": 0.25})
    assert abs(ratio(y, 0) - 1.5) < 0.01 and abs(ratio(y, 1) - 0.25) < 0.01


def test_a_blocks_key_does_not_change_when_a_second_copy_is_added():
    """Faust's own shortname is the shortest unique suffix ('Gain' alone, then 'n1_Gain' once there are two); the key must not follow it."""
    for code, run in ((ONE, lambda p: dd_render.render(ONE, X, SR, p, stereo=True)), (TWO, lambda p: dd_render.render(TWO, X, SR, p, stereo=True))):
        assert abs(ratio(run({"n1_Gain": 2.0}), 0) - 2.0) < 0.01
    assert abs(ratio(wasm(tmp := Path(__import__("tempfile").mkdtemp()), ONE, {"n1_Gain": 2.0}), 0) - 2.0) < 0.01
    assert abs(ratio(wasm(tmp, TWO, {"n1_Gain": 2.0}), 0) - 2.0) < 0.01


def test_flat_chain_keys_are_what_they_were_label_based():
    code = (HERE / "faust/chain_v1.dsp").read_text(encoding="utf-8")
    keys = dd_render.list_params(code, SR)
    assert len(keys) == len(set(keys)) > 100
    for k in ("Highpass_Hz_0_off", "Ring_Hz", "Freq_shift_mix_0_off", "Metal_Q_ring_length", "Output_dB", "Limiter_on"):
        assert k in keys
    labels = re.findall(r'(?:hslider|checkbox)\("(?:\[\d+\])?([^"]+)"', code)
    assert sorted(keys) == sorted({dd_render.short(label) for label in labels})


def test_unknown_keys_are_ignored():
    y = dd_render.render(TWO, X, SR, {"n1_Gain": 2.0, "n9_Nothing": 5, "Gain": 7}, stereo=True)
    assert abs(ratio(y, 0) - 2.0) < 0.01 and abs(ratio(y, 1) - 1.0) < 0.01


def test_without_the_outer_group_a_lone_top_level_group_loses_its_root_so_the_generator_must_always_add_one():
    """Documents why generate() wraps the graph in vgroup("fx", ...): here the address is '/n1/Gain' and the key rule would yield 'Gain'."""
    assert dd_render.list_params(LONE_GROUP, SR) == ["Gain"]
    assert dd_render.list_params(ONE, SR) == ["n1_Gain"]
