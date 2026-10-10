import json

import pytest

from conftest import put
from studio_server import pools
from studio_server.errors import ApiError
from studio_server.jsonio import read_json

MIN = 3


def built(cfg):
    return pools.rebuild(cfg, min_slot_lines=MIN)


def state(cfg):
    return read_json(pools.pools_path(cfg), {})


def test_override_returns_the_previous_routes_and_restore_puts_them_back(pcfg):
    built(pcfg)
    before = state(pcfg)["routes"]
    res = pools.override(pcfg, {"entry": " C2|q", "to": "slot", "slot": "female_human"})
    assert res["changed"] == 2 and set(res["undo"]["previous"]) == {"u13", "u14"}
    assert res["undo"]["previous"]["u13"] == before["u13"] and res["undo"]["previous"]["u13"]["source"] == "auto"
    assert state(pcfg)["routes"]["u13"]["slot"] == "female_human"
    assert pools.restore_routes(pcfg, res["undo"]["previous"]) == {"changed": 2}
    after = state(pcfg)
    assert after["routes"] == before
    assert after["slots"]["male_human"]["lines"] == 8 and after["slots"]["female_human"]["lines"] == 3
    assert pools.summary(pcfg)["queue_entries"] == 2


@pytest.mark.parametrize("previous", [None, {}, [], {"nope": {"to": "narrator"}}, {"u5": {"to": "teleport"}},
                                      {"u5": {"to": "slot", "slot": "gone"}}])
def test_bad_restore_is_400_and_writes_nothing(pcfg, previous):
    built(pcfg)
    before = pools.pools_path(pcfg).read_text(encoding="utf-8")
    with pytest.raises(ApiError) as e:
        pools.restore_routes(pcfg, previous)
    assert e.value.status == 400 and pools.pools_path(pcfg).read_text(encoding="utf-8") == before


def test_merge_records_the_moved_lines_and_unmerge_restores_them(pcfg):
    built(pcfg)
    before = state(pcfg)
    pools.merge_slot(pcfg, "female_human", "male_human")
    assert state(pcfg)["merge_undo"]["female_human"]["guids"] == ["u10", "u11", "u12"]
    res = pools.unmerge_slot(pcfg, "female_human")
    assert res["changed"] == 3 and res["slot"]["id"] == "female_human"
    st = state(pcfg)
    assert st["merged"] == {} and st["merge_undo"] == {}
    assert st["routes"] == before["routes"] and st["slots"] == before["slots"]


def test_unmerge_only_moves_lines_still_in_the_target_and_survives_a_rebuild_in_between(pcfg):
    built(pcfg)
    pools.merge_slot(pcfg, "female_human", "male_human")
    built(pcfg)                                                         # the merge is re-applied
    assert "female_human" not in state(pcfg)["slots"]
    pools.override(pcfg, {"guids": ["u10"], "to": "narrator"})          # a line that has since left
    assert pools.unmerge_slot(pcfg, "female_human")["changed"] == 2
    st = state(pcfg)
    assert st["routes"]["u10"]["to"] == "narrator" and st["routes"]["u11"]["slot"] == "female_human"
    assert built(pcfg)["slots"] and "female_human" in state(pcfg)["slots"]      # and a later rebuild does not merge again


def test_unmerge_undoes_a_chain_in_order_and_rejects_unknown_slots(pcfg):
    built(pcfg)
    pools.create_slot(pcfg, {"name": "Third", "gender": "male"})
    pools.merge_slot(pcfg, "female_human", "male_human")
    pools.merge_slot(pcfg, "male_human", "custom_third")
    assert state(pcfg)["merged"] == {"female_human": "custom_third", "male_human": "custom_third"}
    pools.unmerge_slot(pcfg, "male_human")
    assert state(pcfg)["merged"] == {"female_human": "male_human"}
    pools.unmerge_slot(pcfg, "female_human")
    assert state(pcfg)["merged"] == {}
    for slot in ("female_human", "nope"):
        with pytest.raises(ApiError) as e:
            pools.unmerge_slot(pcfg, slot)
        assert e.value.status == 404


def test_unmerge_of_a_merge_made_before_the_record_existed_is_404(pcfg):
    built(pcfg)
    pools.merge_slot(pcfg, "female_human", "male_human")
    st = state(pcfg)
    st.pop("merge_undo")
    pools.pools_path(pcfg).write_text(json.dumps(st), encoding="utf-8")
    with pytest.raises(ApiError) as e:
        pools.unmerge_slot(pcfg, "female_human")
    assert e.value.status == 404
    assert built(pcfg)["total"] == 15


def test_create_slot_adds_a_designed_voice_that_survives_rebuilds(pcfg):
    built(pcfg)
    manifest_before = read_json(pcfg.voice_design / "design_manifest.json", {})
    rec = pools.create_slot(pcfg, {"name": "Grizzled Sergeant", "gender": "Male", "species": "human", "age": "old"})
    assert rec["id"] == "custom_grizzled_sergeant" and rec["speaker_key"] == "pool_custom_grizzled_sergeant"
    assert rec["lines"] == 0 and rec["custom"] and rec["slug"]
    manifest = read_json(pcfg.voice_design / "design_manifest.json", {})
    assert manifest["pool_custom_grizzled_sergeant"]["candidates"] == [] and manifest["pool_custom_grizzled_sergeant"]["description"]
    assert {k: v for k, v in manifest.items() if k != "pool_custom_grizzled_sergeant"} == manifest_before
    pools.override(pcfg, {"guids": ["u5"], "to": "slot", "slot": rec["id"]})
    assert pools.summary(pcfg)["overrides"] == 1
    for _ in range(2):
        s = built(pcfg)
    by = {x["id"]: x for x in s["slots"]}
    assert by[rec["id"]]["lines"] == 1 and by[rec["id"]]["name"] == "Grizzled Sergeant"


def test_an_empty_custom_slot_survives_a_rebuild_and_can_be_renamed(pcfg):
    built(pcfg)
    pools.create_slot(pcfg, {"name": "Herald", "gender": "female", "description": "A loud herald."})
    pools.rename_slot(pcfg, "custom_herald", "Town herald")
    by = {x["id"]: x for x in built(pcfg)["slots"]}
    assert by["custom_herald"]["name"] == "Town herald" and by["custom_herald"]["lines"] == 0
    assert read_json(pcfg.voice_design / "design_manifest.json", {})["pool_custom_herald"]["description"] == "A loud herald."


@pytest.mark.parametrize("body,status", [
    ({"name": " ", "gender": "male"}, 400), ({"name": "X", "gender": "robot"}, 400), ({"name": "!!!", "gender": "male"}, 400),
    ({"name": "Male human", "gender": "male"}, 400),     # the second create of the same name is a 409 (handled below)
])
def test_create_slot_validation(pcfg, body, status):
    built(pcfg)
    if body["name"] == "Male human":
        pools.create_slot(pcfg, body)
        with pytest.raises(ApiError) as e:
            pools.create_slot(pcfg, body)
        assert e.value.status == 409
        return
    with pytest.raises(ApiError) as e:
        pools.create_slot(pcfg, body)
    assert e.value.status == status


def test_summary_counts_overrides(pcfg):
    built(pcfg)
    assert pools.summary(pcfg)["overrides"] == 0
    pools.override(pcfg, {"guids": ["u1", "u2"], "to": "narrator"})
    assert pools.summary(pcfg)["overrides"] == 2


def test_queue_carries_role_and_playable_samples(pcfg):
    roster = json.loads((pcfg.data / "npc_profile/roster_35b_all.json").read_text(encoding="utf-8"))
    roster[1]["roster"][2]["role"] = "guard captain"
    put(pcfg.data / "npc_profile/roster_35b_all.json", roster)
    put(pcfg.render / "export/index.json", {"u13": {"wav": "wav/u13.wav"}})
    built(pcfg)
    g = {x["key"]: x for x in pools.queue(pcfg)}[" C2|q"]
    assert g["role"] == "guard captain"
    assert g["samples"] == ["Unnamed line 13.", "Unnamed line 14."]                       # still plain strings
    assert g["sample_items"] == [{"guid": "u13", "text": "Unnamed line 13.", "wav": "data/render/export/wav/u13.wav"},
                                 {"guid": "u14", "text": "Unnamed line 14.", "wav": None}]


def test_spot_check_items_and_route_rows_carry_wav_and_entry_names(pcfg):
    put(pcfg.render / "export/index.json", {"u1": {"wav": "wav/u1.wav"}, "u10": {"wav": "wav/u10.wav"}})
    built(pcfg)
    items = pools.spot_check_sample(pcfg, "female_human", seed=1)["items"]
    assert {i["guid"]: i["wav"] for i in items}["u10"] == "data/render/export/wav/u10.wav"
    row = {i["guid"]: i for i in pools.routes_page(pcfg)["items"]}
    assert row["u1"]["wav"] == "data/render/export/wav/u1.wav" and row["u1"]["entry_name"] == "Heinrix" and row["u1"]["entry_label"] == "A"
    assert row["u2"]["wav"] is None and row["u4"]["entry_name"] is None


def test_routes_page_search_confidence_bank_and_entry_filters(pcfg):
    roster = json.loads((pcfg.data / "npc_profile/roster_35b_all.json").read_text(encoding="utf-8"))
    roster[1]["lines"][6]["conf"]["speaker"] = 0.5      # u11
    roster[1]["lines"][0]["conf"]["speaker"] = 0.79     # u5
    put(pcfg.data / "npc_profile/roster_35b_all.json", roster)
    built(pcfg)
    ids = lambda **kw: {i["guid"] for i in pools.routes_page(pcfg, **kw)["items"]}
    assert ids(q="line 11") == {"u11"} and ids(q="HEINRIX") == {"u1", "u2"}
    assert ids(q="tervantias") == {"u3"}                                    # roster name / speaker, not just line text
    assert ids(conf_lt="0.8") == {"u5", "u11"} and ids(conf_lt=0.6) == {"u11"}
    assert ids(bank=True) == {"u1", "u2"} and ids(bank=False) == {"u3"}
    assert ids(entry_name="heinr") == {"u1", "u2"} and ids(entry_name="F", to="slot") == {"u10", "u11", "u12"}
    assert ids(q="line", to="slot", slot="female_human", conf_lt=0.8) == {"u11"}
    with pytest.raises(ApiError) as e:
        pools.routes_page(pcfg, conf_lt="abc")
    assert e.value.status == 400
