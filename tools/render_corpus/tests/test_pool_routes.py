import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pool_routes import load_routes, resolve  # noqa: E402


def write(tmp_path, routes):
    p = tmp_path / "pools.json"
    p.write_text(json.dumps({"routes": routes}), encoding="utf-8")
    return p


def test_missing_file_means_no_routes(tmp_path):
    assert load_routes(tmp_path / "none.json") == {}


def test_load_maps_speakers_slots_and_narrator(tmp_path):
    p = write(tmp_path, {
        "a": {"to": "speaker", "speaker": "Heinrix"},
        "b": {"to": "slot", "slot": "male_human"},
        "c": {"to": "narrator"},
        "d": {"to": "speaker"},               # no speaker name: ignored
    })
    r = load_routes(p)
    assert r == {"a": {"narrator": False, "speaker": "Heinrix"}, "b": {"narrator": False, "speaker": "pool_male_human"},
                 "c": {"narrator": True, "speaker": None}}


def test_resolve_reroutes_only_default_speaker_lines():
    routes = {"a": {"narrator": False, "speaker": "Heinrix"}, "c": {"narrator": True, "speaker": None}}
    assert resolve(routes, "a", "default_speaker", None, False) == ("Heinrix", False, "default_speaker")
    assert resolve(routes, "c", "default_speaker", None, False) == ("narrator", True, "default_speaker")
    assert resolve(routes, "a", "unit", "Ravor", False) == ("Ravor", False, None)           # a named speaker is never rerouted
    assert resolve(routes, "a", "default_speaker", "narrator", True) == ("narrator", True, None)   # narration stays narration


def test_unrouted_lines_are_unchanged():
    assert resolve({}, "zzz", "default_speaker", None, False) == (None, False, None)
    assert resolve({"a": {"narrator": False, "speaker": "X"}}, "other", "default_speaker", None, False) == (None, False, None)
