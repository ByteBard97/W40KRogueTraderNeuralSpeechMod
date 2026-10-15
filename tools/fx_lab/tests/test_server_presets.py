"""The FX Lab page edits flat chain.dsp presets; presets saved from the pedalboard carry a graph and live in presets/, so the page must not list them."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


def test_graph_presets_are_left_out_of_the_flat_page_list():
    saved = {"Flat": {"dsp": "chain.dsp", "params": {"Ring_Hz": 40}, "notes": ""},
             "Board": {"dsp": "presets/board.dsp", "params": {"n1_Gain": 1.0}, "graph": {"version": 1, "nodes": [], "edges": []}, "notes": ""}}
    assert list(server.flat_presets(saved)) == ["Flat"]
    assert "Board" in saved                                                  # the file itself is untouched
