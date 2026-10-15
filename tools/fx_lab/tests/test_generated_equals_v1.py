"""The refactor's proof: today's whole chain, rebuilt as a series graph (blocks.lib + the TypeScript generator), sounds the same as chain_v1.dsp.

Every scenario in scenarios.json with the dry/wet Mix at 1 is rendered through chain_v1.dsp (flat control keys) and through the generated program
(keys `<nodeId>_<label>`, node ids = block ids), both channels, compared from 0.25 s on (the stomps fade in)."""
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

WEB = HERE.parents[0] / "studio/web"
SR = 24000
SKIP_S = 0.25
CHAIN_ORDER = ["highpass", "lowpass", "deesser", "eq", "pitch", "harmonizer", "freqshift", "lowshelf", "vocoder", "compressor", "drive", "resonator", "metal",
               "comb", "bitcrush", "ringmod", "tremolo", "chorus", "wowflutter", "phaser", "dropout", "echo", "static", "reverb", "autopan", "stereochorus",
               "stereophaser", "bassspread"]
TOLERANCE = {"default": (0.9999, 1e-3)}
LOOSER = {"v3 Vocoder": (0.999, 0.03), "v4 Machine: vox-grille servitor": (0.999, 0.03)}          # the vocoder's resonant bands differ in float rounding between block layouts
short = dd_render.short


def series_graph() -> dict:
    ids = ["input", *CHAIN_ORDER, "output"]
    return {"version": 1, "name": "all", "nodes": [{"id": i, "type": i, "x": 0, "y": 0} for i in ids],
            "edges": [{"id": f"e{k}", "source": ids[k], "target": ids[k + 1], "targetPort": 0} for k in range(len(ids) - 1)]}


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    p = tmp_path_factory.mktemp("g") / "graph.json"
    p.write_text(json.dumps(series_graph()))
    r = subprocess.run(["npx", "vite-node", "src/pedalboard/cli.ts", "--", str(p)], cwd=WEB, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.fixture(scope="module")
def mapping():
    """flat v1 key -> generated key, from the catalog (label -> short label, under the block's node id)."""
    cat = json.loads((HERE / "faust/catalog.json").read_text())
    out = {}
    for b in cat["blocks"]:
        for c in b["controls"]:
            out[short(c["label"])] = f"{b['id']}_{short(c['label'])}"
    return out


def compare(a, b):
    n = min(a.shape[1], b.shape[1])
    a, b = a[:, int(SKIP_S * SR):n].astype(np.float64), b[:, int(SKIP_S * SR):n].astype(np.float64)
    corr = min(float(np.corrcoef(a[c], b[c])[0, 1]) if a[c].std() and b[c].std() else 1.0 for c in range(2))
    rel = max(float(np.sqrt(np.mean((a[c] - b[c]) ** 2)) / max(1e-9, np.sqrt(np.mean(a[c] ** 2)))) for c in range(2))
    return corr, rel


def test_the_generated_series_program_is_wrapped_in_the_fx_group_and_has_every_block(generated):
    assert 'process = vgroup("fx",' in generated["code"]
    nodes = {c["nodeId"] for c in generated["controls"]}
    assert nodes == set(CHAIN_ORDER) | {"output"}


def test_default_settings_pass_the_voice_through_in_stereo(generated):
    x = null_test.test_signal()
    y = dd_render.render(generated["code"], x, SR, generated["params"], 0.0, stereo=True)
    assert np.max(np.abs(y[:, int(SKIP_S * SR):] - x[int(SKIP_S * SR):])) < 1e-3


_SCENARIOS = json.loads((HERE / "scenarios.json").read_text())["scenarios"]


@pytest.mark.parametrize("scenario", [s for s in _SCENARIOS if s["params"].get("Mix_0_raw_1_processed", 1) == 1], ids=lambda s: s["name"])
def test_every_scenario_sounds_the_same_through_the_generated_graph(scenario, generated, mapping):
    x = null_test.test_signal()
    tail = 1.0
    v1 = dd_render.render((HERE / "faust/chain_v1.dsp").read_text(), x, SR, scenario["params"], tail, stereo=True)
    params = {**generated["params"], **{mapping[k]: v for k, v in scenario["params"].items() if k in mapping}}
    new = dd_render.render(generated["code"], x, SR, params, tail, stereo=True)
    corr_min, rel_max = next((t for n, t in LOOSER.items() if scenario["name"].startswith(n)), TOLERANCE["default"])
    corr, rel = compare(v1, new)
    assert corr >= corr_min and rel <= rel_max, f"{scenario['name']}: corr {corr:.5f} rel {rel:.5f}"
