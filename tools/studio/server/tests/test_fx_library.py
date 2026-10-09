import json

import pytest

from conftest import put
from studio_server import fx_library, pools, store
from studio_server.errors import ApiError
from studio_server.jsonio import read_json


def test_library_merges_scenarios_and_saved_with_saved_winning(pcfg):
    put(pcfg.data / "fx_lab/presets.json", {"Mine": {"dsp": "chain.dsp", "notes": "n"}, "Clean": {"dsp": "chain.dsp", "notes": "tuned"}})
    lib = {p["name"]: p for p in fx_library.library(pcfg)}
    assert set(lib) == {"Clean", "Mine"}
    assert lib["Clean"]["source"] == "saved" and lib["Clean"]["notes"] == "tuned" and lib["Mine"]["source"] == "saved"
    put(pcfg.data / "fx_lab/presets.json", {})
    assert {p["name"]: p["source"] for p in fx_library.library(pcfg)} == {"Clean": "scenario"}


def test_labels_default_save_and_validate(pcfg):
    assert fx_library.get_labels(pcfg) == {l: [] for l in fx_library.LABELS}
    saved = fx_library.save_labels(pcfg, {"machine": ["Clean", "Mine"], "helmet": ["Mine"]})
    assert saved["machine"] == ["Clean", "Mine"] and saved["ethereal"] == []
    assert fx_library.get_labels(pcfg) == saved
    for bad in ({"machine": ["Nope"]}, {"warp": ["Clean"]}, {"machine": "Clean"}):
        with pytest.raises(ApiError) as e:
            fx_library.save_labels(pcfg, bad)
        assert e.value.status == 400
    assert fx_library.get_labels(pcfg) == saved


def mapped(cfg):
    pools.rebuild(cfg, min_slot_lines=3)
    fx_library.save_labels(cfg, {"machine": ["Clean"], "vox_channel": ["Mine"], "helmet": ["Clean", "Mine"]})


def test_expansion_orders_and_dedupes_labels_and_skips_unmapped(pcfg):
    mapped(pcfg)
    lines = fx_library.expand(pcfg)["lines"]
    assert lines["u5"] == ["Clean"]
    assert lines["u6"] == ["Mine", "Clean"]                    # vox_channel then helmet, "Mine" not repeated
    assert lines["u10"] == ["Clean"]                           # machine twice, one preset
    assert "u12" not in lines and "u7" not in lines            # ethereal unmapped; u7 has no labels


def test_preview_reports_unmapped_labels_and_writes_nothing(pcfg):
    mapped(pcfg)
    p = fx_library.preview(pcfg)
    assert p["lines"] == 3 and p["unmapped_labels"] == {"ethereal": 1} and p["sample"]
    assert not (pcfg.data / "fx_lab/assignments.json").exists()


def test_speaker_assignments_come_from_the_active_profile_only(pcfg):
    mapped(pcfg)
    store.save_profile(pcfg, "pasqal", {"source": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "t", "origin": "real"}, "fx": ["Clean"]})
    assert fx_library.expand(pcfg)["speakers"] == {}           # saved but not set active
    store.set_active(pcfg, "pasqal")
    assert fx_library.expand(pcfg)["speakers"] == {"Pasqal": ["Clean"]}


def test_write_creates_the_file_and_keeps_a_backup_of_the_previous_one(pcfg):
    mapped(pcfg)
    out = fx_library.write(pcfg)
    path = pcfg.data / "fx_lab/assignments.json"
    assert out["lines"] == 3 and json.loads(path.read_text(encoding="utf-8"))["lines"]["u5"] == ["Clean"]
    assert not (pcfg.data / "fx_lab/assignments.json.bak").exists()
    fx_library.save_labels(pcfg, {"machine": ["Mine"]})
    fx_library.write(pcfg)
    assert read_json(pcfg.data / "fx_lab/assignments.json.bak", {})["lines"]["u5"] == ["Clean"]
    assert read_json(path, {})["lines"]["u5"] == ["Mine"]


def test_expansion_without_a_roster_is_a_clear_404(pcfg):
    (pcfg.data / "npc_profile/roster_35b_all.json").unlink()
    with pytest.raises(ApiError) as e:
        fx_library.expand(pcfg)
    assert e.value.status == 404
