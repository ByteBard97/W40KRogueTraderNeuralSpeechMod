import json

import pytest

import time

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
    assert out["backup"] is None and not list(path.parent.glob("*.bak*"))
    fx_library.save_labels(pcfg, {"machine": ["Mine"]})
    out = fx_library.write(pcfg)
    assert read_json(path.parent / out["backup"], {})["lines"]["u5"] == ["Clean"]
    assert read_json(path, {})["lines"]["u5"] == ["Mine"]


def test_expansion_without_a_roster_is_a_clear_404(pcfg):
    (pcfg.data / "npc_profile/roster_35b_all.json").unlink()
    with pytest.raises(ApiError) as e:
        fx_library.expand(pcfg)
    assert e.value.status == 404


@pytest.mark.parametrize("name,fam,ver", [
    ("Clean", "Clean", "v1"), ("Machine: servitor", "Machine", "v1"), ("v2 Machine: Dalek (1963 recipe)", "Machine", "v2"),
    ("Helmet + vox (astartes over comms)", "Helmet", "v1"), ("v4 Vox: field radio with dropouts", "Vox", "v4"),
    ("Phaser test: classic 4-stage (Phase 90 style)", "Phaser test", "v1"), ("V3 Vocoder: x", "Vocoder", "v3")])
def test_family_and_version_from_the_name(name, fam, ver):
    assert fx_library.family_version(name) == (fam, ver)


def test_library_reports_family_version_and_explicit_keys_win(pcfg):
    put(pcfg.data / "fx_lab/presets.json", {"v3 Mine: x": {"family": "Custom", "version": "v9"}, "Plain": {}})
    lib = {p["name"]: p for p in fx_library.library(pcfg)}
    assert (lib["Clean"]["family"], lib["Clean"]["version"]) == ("Clean", "v1")
    assert (lib["v3 Mine: x"]["family"], lib["v3 Mine: x"]["version"]) == ("Custom", "v9")
    assert (lib["Plain"]["family"], lib["Plain"]["version"]) == ("Plain", "v1")


def test_usage_counts_lines_and_voices_per_label(pcfg):
    mapped(pcfg)
    u = fx_library.usage(pcfg)
    assert u["pools_built"] is True
    assert u["labels"]["machine"] == {"lines": 2, "speakers": 2, "presets": 1}      # u5 (male slot), u10 (female slot)
    assert u["labels"]["vox_channel"]["lines"] == 1 and u["labels"]["ethereal"] == {"lines": 1, "speakers": 1, "presets": 0}
    assert u["labels"]["monstrous"]["lines"] == 0


def test_usage_before_pools_are_built_groups_by_roster_entry(pcfg):
    fx_library.save_labels(pcfg, {"machine": ["Clean"]})
    u = fx_library.usage(pcfg)
    assert u["pools_built"] is False and u["labels"]["machine"]["lines"] == 2 and u["labels"]["machine"]["speakers"] == 2


def test_diff_lists_changed_voices_first_with_now_and_after(pcfg):
    mapped(pcfg)
    d = fx_library.diff(pcfg)
    assert d["file_mtime"] is None and d["changed"] == len(d["rows"]) - sum(1 for r in d["rows"] if not r["changed"])
    assert d["changed"] >= 1 and all(r["changed"] for r in d["rows"])      # nothing written yet: every voice changes
    assert all(r["now"] == [] for r in d["rows"]) and {tuple(r["after"]) for r in d["rows"]} >= {("Clean",)}
    fx_library.write(pcfg)
    d = fx_library.diff(pcfg)
    assert d["changed"] == 0 and d["file_mtime"] and all(not r["changed"] and r["now"] == r["after"] for r in d["rows"])
    fx_library.save_labels(pcfg, {"machine": ["Mine"]})
    d = fx_library.diff(pcfg)
    assert d["changed"] >= 1 and d["rows"][0]["changed"] and d["rows"][0]["now"] == ["Clean"] and d["rows"][0]["after"] == ["Mine"]


def test_diff_includes_active_profile_speakers(pcfg):
    mapped(pcfg)
    store.save_profile(pcfg, "pasqal", {"source": {"wav": "data/voices/wav/Pasqal/E1.wav", "text": "t", "origin": "real"}, "fx": ["Clean"]})
    store.set_active(pcfg, "pasqal")
    row = next(r for r in fx_library.diff(pcfg)["rows"] if r["kind"] == "profile")
    assert (row["speaker"], row["now"], row["after"], row["changed"]) == ("Pasqal", [], ["Clean"], True)


def test_write_reports_backup_and_affected_speakers_and_backups_are_listed(pcfg):
    mapped(pcfg)
    first = fx_library.write(pcfg)
    assert first["affected_speakers"] >= 1 and first["backup"] is None
    fx_library.save_labels(pcfg, {"machine": ["Mine"]})              # backs up fx_labels.json too
    second = fx_library.write(pcfg)
    assert second["affected_speakers"] >= 1 and fx_library.BACKUP_NAME.match(second["backup"])
    names = [(b["kind"], b["name"]) for b in fx_library.backups(pcfg)]
    assert ("assignments", second["backup"]) in names and any(k == "labels" for k, _ in names)
    # same-second writes never overwrite an earlier backup
    third = fx_library.write(pcfg)
    assert third["backup"] != second["backup"] and len({n for _, n in [(b["kind"], b["name"]) for b in fx_library.backups(pcfg)]}) == len(fx_library.backups(pcfg))


def test_restore_puts_the_backup_back_and_backs_up_what_it_replaces(pcfg):
    mapped(pcfg)
    fx_library.write(pcfg)
    fx_library.save_labels(pcfg, {"machine": ["Mine"]})
    out = fx_library.write(pcfg)
    live = pcfg.data / "fx_lab/assignments.json"
    assert read_json(live, {})["lines"]["u5"] == ["Mine"]
    r = fx_library.restore(pcfg, out["backup"])
    assert r["kind"] == "assignments" and read_json(live, {})["lines"]["u5"] == ["Clean"]
    assert read_json(live.parent / r["backup"], {})["lines"]["u5"] == ["Mine"]      # the undo of the restore
    lab = next(b for b in fx_library.backups(pcfg) if b["kind"] == "labels")
    r = fx_library.restore(pcfg, lab["name"])
    assert r["kind"] == "labels" and fx_library.get_labels(pcfg)["machine"] == ["Clean"]


@pytest.mark.parametrize("name", ["../x.bak.json", "assignments.json", "nope.bak.json", "", None, "assignments.2026-01-01T00-00-00.bak.json"])
def test_restore_rejects_unknown_or_unsafe_names(pcfg, name):
    with pytest.raises(ApiError) as e:
        fx_library.restore(pcfg, name)
    assert e.value.status == 404
