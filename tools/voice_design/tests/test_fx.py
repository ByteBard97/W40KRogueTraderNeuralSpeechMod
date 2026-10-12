"""FX chain tests. Need numpy + scipy (skipped under a python without scipy); the parity test also needs node.

Run: PYTHONPATH=... tools/scorer/.venv-scorer/bin/python -m pytest  (or the roguetts env) tools/voice_design/tests/test_fx.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import fx  # noqa: E402

SR = 24000
N = 12000
PRESETS = {
    "off": {},
    "bandpass": {"hp": 300, "lp": 3400},
    "robot": {"ring": {"hz": 55, "mix": 0.8}, "crush": {"bits": 7, "hold": 3}, "drive": 0.4},
    "echo": {"echo": {"ms": 90, "fb": 0.45, "mix": 0.5}, "trem": {"hz": 6, "depth": 0.4}},
    "loud": {"drive": 1.0, "hp": 120},
    "wetdry": {"ring": {"hz": 55, "mix": 1}, "echo": {"ms": 90, "fb": 0.4, "mix": 0.5}, "rrev": {"decay": 0.5, "mix": 0.5}, "mix": 0.4},
    "chorus": {"chorus": {"ms": 3, "hz": 0.9, "mix": 0.6}, "hp": 100},
    "rrev": {"rrev": {"decay": 0.8, "mix": 0.6}, "trem": {"hz": 5, "depth": 0.15}},
}


def test_signal():
    n = np.arange(N)
    x = (0.6 * np.sin(2 * np.pi * 220 * n / SR) + 0.3 * np.sin(2 * np.pi * 1330 * n / SR + 0.5)
         + 0.2 * np.sin(2 * np.pi * 3100 * n / SR)).astype(np.float32)
    return x


def test_defaults_are_a_noop():
    x = test_signal() * 0.5  # below the peak limit, so an empty preset must return it unchanged
    assert np.allclose(fx.apply_fx(x, SR, {}), x, atol=1e-6)


def test_peak_is_limited_and_echo_extends():
    x = test_signal() * 3
    y = fx.apply_fx(x, SR, {"echo": {"ms": 100, "fb": 0.5, "mix": 0.6}})
    assert np.max(np.abs(y)) <= fx.PEAK + 1e-6
    assert len(y) > len(x)


def test_bandpass_attenuates_out_of_band():
    n = np.arange(N)
    low = np.sin(2 * np.pi * 60 * n / SR).astype(np.float32) * 0.5
    y = fx.apply_fx(low, SR, {"hp": 600})
    assert np.sqrt(np.mean(y[2000:] ** 2)) < 0.02


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_python_matches_browser_dsp():
    js = f"""
    const {{applyFx}} = require({json.dumps(str(HERE / 'dsp.js'))});
    const sr = {SR}, N = {N};
    const x = new Float32Array(N);
    for (let n = 0; n < N; n++) x[n] = 0.6*Math.sin(2*Math.PI*220*n/sr) + 0.3*Math.sin(2*Math.PI*1330*n/sr+0.5) + 0.2*Math.sin(2*Math.PI*3100*n/sr);
    const presets = {json.dumps(PRESETS)};
    const out = {{}};
    for (const [k, p] of Object.entries(presets)) out[k] = Array.from(applyFx(x, sr, p));
    process.stdout.write(JSON.stringify(out));
    """
    res = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    js_out = json.loads(res.stdout)
    x = test_signal()
    for name, preset in PRESETS.items():
        py = fx.apply_fx(x, SR, preset)
        jv = np.array(js_out[name], dtype=np.float32)
        assert len(py) == len(jv), name
        assert np.max(np.abs(py - jv)) < 2e-3, (name, float(np.max(np.abs(py - jv))))
        assert np.mean(np.abs(py - jv)) < 1e-5, name


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_apply_fx_batch_is_incremental_and_stretches(tmp_path):
    sf = pytest.importorskip("soundfile")
    import apply_fx as af
    src = tmp_path / "export"
    (src / "wav").mkdir(parents=True)
    sf.write(str(src / "wav/g1.wav"), test_signal() * 0.5, SR)
    sf.write(str(src / "wav/g2.wav"), test_signal() * 0.5, SR)
    (src / "index.json").write_text(json.dumps({
        "g1": {"wav": "wav/g1.wav", "speaker": "Pasqal"}, "g2": {"wav": "wav/g2.wav", "speaker": "Other"}}))
    out = tmp_path / "export_fx"
    presets = {"Pasqal": {"fx": {"hp": 200}, "speed": 1.25}}
    assert af.process(src, out, presets) == (1, 0)
    assert af.process(src, out, presets) == (0, 1)  # unchanged preset: nothing redone
    idx = json.loads((out / "index.json").read_text())
    assert list(idx) == ["g1"]  # speakers without a preset are left to the raw export
    y, sr = sf.read(str(out / "wav/g1.wav"))
    assert sr == SR and abs(len(y) / N - 1 / 1.25) < 0.03  # 25% faster = 20% shorter
    presets["Pasqal"]["speed"] = 1.1
    assert af.process(src, out, presets) == (1, 0)  # changed preset: redone


def test_reverse_reverb_swells_before_the_sound():
    n = np.arange(N)
    burst = np.zeros(N, dtype=np.float32)
    burst[6000:6600] = 0.5 * np.sin(2 * np.pi * 440 * n[:600] / SR)
    y = fx.apply_fx(burst, SR, {"rrev": {"decay": 0.6, "mix": 1.0}})
    tail = int(0.6 * SR)
    assert len(y) == N + tail
    onset = 6000 + tail                                    # dry burst moved right by the tail
    before = np.sqrt(np.mean(y[onset - 3000:onset - 100] ** 2))   # swell energy just before the burst
    after = np.sqrt(np.mean(y[onset + 3000:onset + 6000] ** 2))   # nothing much long after (reverb ran backwards)
    assert before > 3 * after


def test_wet_dry_mix_blends_with_the_aligned_original():
    x = test_signal() * 0.5
    chain = {"ring": {"hz": 55, "mix": 1}, "rrev": {"decay": 0.5, "mix": 0.5}}
    lead = int(0.5 * SR)
    dry_only = fx.apply_fx(x, SR, {**chain, "mix": 0})
    assert len(dry_only) == len(x) + lead
    assert np.allclose(dry_only[lead:lead + N], x, atol=1e-6) and np.allclose(dry_only[:lead], 0, atol=1e-9)
    full = fx.apply_fx(x, SR, {**chain, "mix": 1})
    assert np.allclose(full, fx.apply_fx(x, SR, chain), atol=1e-9)         # mix 1 is the plain chain
    half = fx.apply_fx(x, SR, {**chain, "mix": 0.5})
    assert np.allclose(half, 0.5 * full + 0.5 * dry_only, atol=1e-5)       # linear blend
