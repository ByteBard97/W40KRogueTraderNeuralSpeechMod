import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studio_server import pedalboard  # noqa: E402
from studio_server.config import Config  # noqa: E402
from studio_server.errors import ApiError  # noqa: E402
from studio_server.routes import build_router  # noqa: E402

CODE = 'import("stdfaust.lib");\nprocess = _,_;\n'


@pytest.fixture
def cfg(tmp_path):
    return Config(root=tmp_path)


def graph(name="g1", **over):
    return {"version": 1, "name": name, "nodes": [{"id": "n1"}], "edges": [], **over}


def body(name="g1", **over):
    return {"graph": graph(name), "code": CODE, "params": {"n1_gain": 3.5}, **over}


def faust_files(cfg):
    d = cfg.root / "tools/fx_lab/faust"
    d.mkdir(parents=True, exist_ok=True)
    (d / "blocks.lib").write_text("node_gain = _;\n", encoding="utf-8")
    (d / "catalog.json").write_text(json.dumps({"blocks": [{"id": "gain"}]}), encoding="utf-8")


def presets(cfg):
    return json.loads((cfg.data / "fx_lab/presets.json").read_text(encoding="utf-8"))


def snapshot(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_blocks_returns_lib_and_catalog(cfg):
    faust_files(cfg)
    out = pedalboard.blocks(cfg)
    assert out == {"lib": "node_gain = _;\n", "catalog": {"blocks": [{"id": "gain"}]}}


@pytest.mark.parametrize("missing", ["blocks.lib", "catalog.json"])
def test_blocks_404_when_a_file_is_missing(cfg, missing):
    faust_files(cfg)
    (cfg.root / "tools/fx_lab/faust" / missing).rename(cfg.root / "elsewhere")
    with pytest.raises(ApiError) as e:
        pedalboard.blocks(cfg)
    assert e.value.status == 404 and missing in e.value.message


def test_list_is_empty_when_the_folder_is_missing(cfg):
    assert pedalboard.list_graphs(cfg) == []


def test_list_is_newest_first(cfg):
    for i, n in enumerate(["old", "mid", "new"]):
        pedalboard.save_graph(cfg, body(n))
        os.utime(cfg.data / f"fx_lab/graphs/{n}.json", (1_700_000_000 + i * 100,) * 2)
    out = pedalboard.list_graphs(cfg)
    assert [g["name"] for g in out] == ["new", "mid", "old"]
    assert out[0]["updated"] > out[2]["updated"]


def test_save_then_load_round_trips_and_writes_all_three_files(cfg):
    out = pedalboard.save_graph(cfg, body(notes="warm"))
    assert out == {"name": "g1", "dsp": "presets/g1.dsp", "saved": True}
    assert pedalboard.load_graph(cfg, "g1") == graph()
    assert (cfg.root / "tools/fx_lab/faust/presets/g1.dsp").read_text(encoding="utf-8") == CODE
    assert presets(cfg)["g1"] == {"dsp": "presets/g1.dsp", "params": {"n1_gain": 3.5}, "graph": graph(), "notes": "warm"}


def test_load_unknown_graph_is_404(cfg):
    with pytest.raises(ApiError) as e:
        pedalboard.load_graph(cfg, "nope")
    assert e.value.status == 404


def test_saving_twice_overwrites_and_keeps_other_presets(cfg):
    other = {"dsp": "chain.dsp", "params": {"a": 1}, "notes": "mine"}
    (cfg.data / "fx_lab").mkdir(parents=True)
    (cfg.data / "fx_lab/presets.json").write_text(json.dumps({"Mine": other}), encoding="utf-8")
    pedalboard.save_graph(cfg, body())
    pedalboard.save_graph(cfg, {**body(), "code": CODE + "// v2\n", "params": {"n1_gain": 9}})
    p = presets(cfg)
    assert p["Mine"] == other and set(p) == {"Mine", "g1"}
    assert p["g1"]["params"] == {"n1_gain": 9} and p["g1"]["notes"] == ""
    assert "// v2" in (cfg.root / "tools/fx_lab/faust/presets/g1.dsp").read_text(encoding="utf-8")


def test_a_backup_of_presets_is_made_once_per_interval(cfg):
    (cfg.data / "fx_lab").mkdir(parents=True)
    (cfg.data / "fx_lab/presets.json").write_text(json.dumps({"Mine": {}}), encoding="utf-8")
    pedalboard.save_graph(cfg, body())
    pedalboard.save_graph(cfg, body())
    backups = list((cfg.data / "fx_lab").glob("presets.*.bak.json"))
    assert len(backups) == 1 and json.loads(backups[0].read_text(encoding="utf-8")) == {"Mine": {}}


def test_no_backup_when_presets_is_missing_or_empty(cfg):
    pedalboard.save_graph(cfg, body("a"))              # first save: nothing to back up
    assert not list((cfg.data / "fx_lab").glob("presets.*.bak.json"))


@pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "", ".hidden", "x" * 61, "a b", "a.b", "g\n", None, 5])
def test_bad_names_are_rejected_before_anything_is_written(cfg, name):
    before = snapshot(cfg.root)
    with pytest.raises(ApiError) as e:
        pedalboard.save_graph(cfg, {**body(), "graph": graph(name)})
    assert e.value.status == 400
    assert snapshot(cfg.root) == before
    if isinstance(name, str):
        with pytest.raises(ApiError) as e:
            pedalboard.load_graph(cfg, name)
        assert e.value.status == 400


@pytest.mark.parametrize("bad", [
    {"graph": "x"},
    {"graph": graph(version=2)},
    {"graph": graph(version=True)},
    {"graph": graph(nodes={})},
    {"graph": graph(edges=None)},
    {"code": ""},
    {"code": "import(\"stdfaust.lib\");"},
    {"code": 5},
    {"params": []},
    {"params": {"a": "1"}},
    {"params": {"a": {"b": 1}}},
    {"params": {"a": True}},
    {"params": None},
    {"notes": 5},
])
def test_bad_payloads_are_rejected_with_nothing_written(cfg, bad):
    before = snapshot(cfg.root)
    with pytest.raises(ApiError) as e:
        pedalboard.save_graph(cfg, {**body(), **bad})
    assert e.value.status == 400
    assert snapshot(cfg.root) == before


def test_a_failed_preset_write_leaves_the_earlier_presets_file_intact(cfg, monkeypatch):
    pedalboard.save_graph(cfg, body("keep"))
    original = (cfg.data / "fx_lab/presets.json").read_bytes()
    real, calls = pedalboard.write_json_atomic, []

    def flaky(path, obj):
        calls.append(path.name)
        if len(calls) == 2:                              # graph is write 1, presets.json is write 2
            raise OSError("disk full")
        real(path, obj)

    monkeypatch.setattr(pedalboard, "write_json_atomic", flaky)
    with pytest.raises(OSError):
        pedalboard.save_graph(cfg, body("other"))
    assert calls[-1] == "presets.json"
    assert (cfg.data / "fx_lab/presets.json").read_bytes() == original
    assert not list((cfg.data / "fx_lab").glob("*.tmp"))


def test_router_serves_blocks_and_saves_graphs(cfg):
    router = build_router()
    status, out = router.dispatch("GET", "/api/pedalboard/blocks", {}, {}, cfg, None)
    assert status == 404 and "error" in out
    faust_files(cfg)
    status, out = router.dispatch("GET", "/api/pedalboard/blocks", {}, {}, cfg, None)
    assert status == 200 and out["lib"].startswith("node_gain")
    status, out = router.dispatch("POST", "/api/pedalboard/graphs", {}, body(), cfg, None)
    assert (status, out["saved"]) == (200, True)
    status, out = router.dispatch("GET", "/api/pedalboard/graphs", {}, {}, cfg, None)
    assert status == 200 and [g["name"] for g in out] == ["g1"]
    status, out = router.dispatch("GET", "/api/pedalboard/graphs/g1", {}, {}, cfg, None)
    assert status == 200 and out == graph()
    status, out = router.dispatch("POST", "/api/pedalboard/graphs", {}, body("../x"), cfg, None)
    assert status == 400
    status, _ = router.dispatch("GET", "/api/pedalboard/graphs/missing", {}, {}, cfg, None)
    assert status == 404
