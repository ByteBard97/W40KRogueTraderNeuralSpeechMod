import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_server import starters  # noqa: E402
from studio_server.config import Config  # noqa: E402
from studio_server.routes import build_router  # noqa: E402

G = {"version": 1, "name": "x", "nodes": [], "edges": []}


@pytest.fixture
def cfg(tmp_path):
    return Config(root=tmp_path)


def put(cfg, slug, name, category, desc="d", raw=None):
    d = cfg.root / "tools/fx_lab/starters"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.json").write_text(raw if raw is not None else json.dumps({"name": name, "description": desc, "category": category, "graph": G}), encoding="utf-8")


def test_missing_folder_gives_an_empty_list(cfg):
    assert starters.list_starters(cfg) == []


def test_sorted_by_category_order_then_name_with_the_agreed_shape(cfg):
    put(cfg, "t", "Phaser", "Test")
    put(cfg, "rt-b", "RT B", "Rogue Trader")
    put(cfg, "m-b", "Machine: beta", "Machine")
    put(cfg, "m-a", "Machine: alpha", "Machine")
    put(cfg, "odd", "Odd", "Unlisted")
    out = starters.list_starters(cfg)
    assert [s["slug"] for s in out] == ["m-a", "m-b", "rt-b", "t", "odd"]
    assert out[0] == {"slug": "m-a", "name": "Machine: alpha", "description": "d", "category": "Machine", "graph": G}


@pytest.mark.parametrize("raw", ["{not json", "[]", json.dumps({"name": "x", "category": "Machine"}), json.dumps({"name": 3, "category": "Test", "graph": G})])
def test_a_malformed_file_is_skipped_with_a_note(cfg, raw):
    put(cfg, "good", "Good", "Machine")
    put(cfg, "bad", "", "", raw=raw)
    notes: list[str] = []
    out = starters.list_starters(cfg, notes)
    assert [s["slug"] for s in out] == ["good"]
    assert len(notes) == 1 and "bad.json" in notes[0]


def test_route_serves_the_list(cfg):
    put(cfg, "a", "A", "Vox")
    status, out = build_router().dispatch("GET", "/api/pedalboard/starters", {}, {}, cfg, None)
    assert status == 200 and [s["slug"] for s in out] == ["a"]


def test_the_shipped_starters_load_without_notes():
    notes: list[str] = []
    out = starters.list_starters(Config(), notes)
    assert notes == [] and len(out) >= 49 and all(s["category"] in starters.CATEGORY_ORDER for s in out)
