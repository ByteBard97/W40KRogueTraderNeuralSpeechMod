"""The shipped starting-point graphs (tools/fx_lab/starters): valid, compile, sound like the scenarios they were migrated from, and the Rogue Trader ones behave.

All starters go through the TypeScript generator in one process (generate_all), so the file stays well under a minute."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dd_render  # noqa: E402
import migrate_scenarios as ms  # noqa: E402
import null_test  # noqa: E402
from test_generated_equals_v1 import CHAIN_ORDER, LOOSER, TOLERANCE, compare  # noqa: E402

SR = 24000
PEAK_LIMIT = 0.99
STEREO_CORR_MAX = 0.9999
# These two keep a decaying start-up transient of the stomp fade-ins (the largest difference sits at the first compared sample and dies away), so the
# 0.25 s cut leaves a little more residue than the 1e-3 bound; correlation is still above 0.99999.
TRANSIENT_LOOSER = {"v2 Machine: Necron": (0.9999, 3e-3), "v2 Ethereal: psyker": (0.9999, 3e-3)}
PASQAL_CORR = (0.4, 0.98)
STARTERS = sorted(ms.STARTERS.glob("*.json"))
_SCENARIOS = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
_RECIPES = json.loads((HERE / "rt_preset_recipes.json").read_text(encoding="utf-8"))["recipes"]
V1 = (HERE / "faust/chain_v1.dsp").read_text(encoding="utf-8")


def load(slug: str) -> dict:
    return json.loads((ms.STARTERS / f"{slug}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def generated() -> dict:
    """slug -> generator result for every committed starter."""
    return ms.generate_all({p.stem: json.loads(p.read_text(encoding="utf-8"))["graph"] for p in STARTERS})


def speech_like(seconds: float = 4.0) -> np.ndarray:
    """A buzzy voiced source with syllable-rate gating and formant-ish colouring; enough to exercise bass and stereo blocks."""
    n = np.arange(int(SR * seconds))
    f0 = 110 + 20 * np.sin(2 * np.pi * 0.7 * n / SR)
    phase = 2 * np.pi * np.cumsum(f0) / SR
    voiced = sum(np.sin(k * phase) / k for k in range(1, 30))
    env = np.clip(np.sin(2 * np.pi * 3.5 * n / SR), 0, None) ** 0.7
    noise = np.random.default_rng(1).standard_normal(len(n)) * 0.05
    return (0.25 * env * voiced / 3 + noise * env).astype(np.float32)


def noise(seconds: float = 6.0) -> np.ndarray:
    return (np.random.default_rng(0).standard_normal(int(SR * seconds)) * 0.1).astype(np.float32)


def lr_corr(y: np.ndarray, skip: float = 0.5) -> float:
    y = y[:, int(skip * SR):].astype(np.float64)
    return float(np.corrcoef(y[0], y[1])[0, 1])


def render(g: dict, x: np.ndarray, tail: float = 0.0) -> np.ndarray:
    return dd_render.render(g["code"], x, SR, g["params"], tail, stereo=True)


def test_there_is_one_starter_per_scenario_and_recipe():
    assert len(STARTERS) == len(_SCENARIOS) + len(_RECIPES)


def test_every_starter_has_the_agreed_shape_and_a_valid_generated_graph(generated):
    for p in STARTERS:
        s = json.loads(p.read_text(encoding="utf-8"))
        assert set(s) == {"name", "description", "category", "graph"}, p.name
        assert s["category"] in ms.CATEGORY_ORDER, p.name
        assert s["graph"]["name"] == p.stem
        assert "error" not in generated[p.stem], f"{p.name}: {generated[p.stem]}"
        assert 'process = vgroup("fx",' in generated[p.stem]["code"]


def test_every_starter_compiles_and_renders_finite_sound(generated):
    x = null_test.test_signal(seconds=0.5)
    for slug, g in generated.items():
        y = render(g, x, 0.1)
        assert np.isfinite(y).all(), slug


def test_ids_are_block_ids_and_neutral_pedals_are_left_out():
    cat = {b["id"] for b in json.loads((HERE / "faust/catalog.json").read_text(encoding="utf-8"))["blocks"]}
    for p in STARTERS:
        nodes = json.loads(p.read_text(encoding="utf-8"))["graph"]["nodes"]
        assert all(n["id"] == n["type"] and n["id"] in cat for n in nodes), p.name
    assert [n["id"] for n in load("clean")["graph"]["nodes"]] == ["input", "output"]


@pytest.mark.parametrize("scenario", _SCENARIOS, ids=lambda s: s["name"])
def test_every_scenario_sounds_the_same_through_its_starter(scenario, generated):
    """Includes the scenarios with Mix below 1 (rebuilt as a Mix 2 node), which the all-pedals-in-series test skips."""
    x = null_test.test_signal()
    tail = 1.0
    v1 = dd_render.render(V1, x, SR, scenario["params"], tail, stereo=True)
    new = render(generated[ms.slug_of(scenario["name"])], x, tail)
    corr_min, rel_max = next((t for n, t in {**LOOSER, **TRANSIENT_LOOSER}.items() if scenario["name"].startswith(n)), TOLERANCE["default"])     # the vocoder's bands differ in float rounding between layouts
    corr, rel = compare(v1, new)
    assert corr >= corr_min and rel <= rel_max, f"{scenario['name']}: corr {corr:.5f} rel {rel:.5f}"


@pytest.mark.parametrize("recipe", _RECIPES, ids=lambda r: r["name"])
def test_rogue_trader_starters_stay_under_the_limiter(recipe, generated):
    g = generated[ms.slug_of(recipe["name"])]
    for x in (null_test.test_signal(), speech_like()):
        y = render(g, x, 1.0)
        assert np.isfinite(y).all()
        assert np.max(np.abs(y)) < PEAK_LIMIT, recipe["name"]


STEREO_BLOCKS = {"bassspread", "stereochorus", "stereophaser", "autopan"}


@pytest.mark.parametrize("recipe", _RECIPES, ids=lambda r: r["name"])
def test_rogue_trader_starters_with_stereo_blocks_differ_between_the_channels(recipe, generated):
    slug = ms.slug_of(recipe["name"])
    active = {n["id"] for n in load(slug)["graph"]["nodes"] if n["id"] in STEREO_BLOCKS and n.get("on", True)}
    if not active:
        pytest.skip("no stereo block in this recipe")
    assert lr_corr(render(generated[slug], noise(), 1.0)) < STEREO_CORR_MAX, f"{recipe['name']}: {sorted(active)}"


def test_the_pasqal_target_starter_lands_between_mono_and_wide(generated):
    """Aimed at the game's measured left/right correlation of 0.77; the band is wide because the target is rough."""
    y = render(generated["rt-tech-priest-pasqal-target-stereo"], speech_like(6.0), 0.5)
    lo, hi = PASQAL_CORR
    assert lo < lr_corr(y) < hi, lr_corr(y)


def test_check_passes():
    r = subprocess.run([sys.executable, str(HERE / "migrate_scenarios.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_no_two_pedals_in_a_starter_overlap_on_the_canvas():
    """A pedal is 220 px wide and as tall as its controls need (migrate_scenarios.node_height); the layout must keep them apart."""
    import migrate_scenarios as M
    catalog = json.loads((HERE / "faust/catalog.json").read_text())
    blocks = {b["id"]: b for b in catalog["blocks"]}
    for f in sorted((HERE / "starters").glob("*.json")):
        nodes = json.loads(f.read_text())["graph"]["nodes"]
        rects = [(n["id"], n["x"], n["y"], n["x"] + M.NODE_WIDTH, n["y"] + (M.node_height(blocks[n["type"]]) if n["type"] != "input" else 60)) for n in nodes]
        for i, (a, ax0, ay0, ax1, ay1) in enumerate(rects):
            for b, bx0, by0, bx1, by1 in rects[i + 1:]:
                assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0, f"{f.name}: {a} overlaps {b}"
