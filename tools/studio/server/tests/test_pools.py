import json

import pytest

from conftest import put
from studio_server import pools
from studio_server.errors import ApiError
from studio_server.jsonio import read_json

MIN = 3     # slots need 3 lines in the fixture (the real default is 40)


def built(cfg, **kw):
    return pools.rebuild(cfg, min_slot_lines=MIN, **kw)


def state(cfg):
    return read_json(pools.pools_path(cfg), {})


def test_summary_before_build_is_a_clear_404(pcfg):
    with pytest.raises(ApiError) as e:
        pools.summary(pcfg)
    assert e.value.status == 404 and "rebuild" in e.value.message


def test_rebuild_routes_every_unnamed_line_and_counts_destinations(pcfg):
    s = built(pcfg)
    assert s["total"] == 15
    assert s["destinations"] == {"narrator": 1, "speaker_bank": 2, "speaker_nobank": 1, "slot": 11}
    ids = {x["id"]: x["lines"] for x in s["slots"]}
    assert ids == {"male_human": 8, "female_human": 3, "female_machine": 0}     # u13-u15 (unknown gender, no entry) join the male majority
    assert s["queue_lines"] == 3 and s["queue_entries"] == 2


def test_a_female_machine_slot_always_exists_even_with_no_lines(pcfg):
    s = built(pcfg)
    fm = next(x for x in s["slots"] if x["id"] == "female_machine")
    assert fm["lines"] == 0 and fm["name"] == "Female machine" and fm["gender"] == "female" and fm["species"] == "machine"
    manifest = read_json(pcfg.voice_design / "design_manifest.json", {})
    assert manifest["pool_female_machine"]["gender"] == "Female" and "cyborg" in manifest["pool_female_machine"]["description"].lower()


def test_rebuild_registers_each_slot_as_a_designed_speaker_once(pcfg):
    built(pcfg)
    built(pcfg)
    manifest = read_json(pcfg.voice_design / "design_manifest.json", {})
    assert manifest["pool_male_human"]["slug"] == "pool_male_human" and manifest["pool_male_human"]["candidates"] == []
    assert manifest["pool_male_human"]["description"] and manifest["pool_male_human"]["text"] == pools.SAMPLE_TEXT
    assert "Muaran" in manifest and len([k for k in manifest if k.startswith("pool_")]) == 3
    from studio_server import speakers
    names = {s["name"]: s for s in speakers.list_speakers(pcfg)}
    assert names["pool_male_human"]["origin"] == "designed"


def test_rebuild_never_discards_overrides_or_renamed_slots(pcfg):
    built(pcfg)
    pools.override(pcfg, {"guids": ["u5"], "to": "slot", "slot": "female_human"})
    pools.rename_slot(pcfg, "female_human", "Women of the Expanse")
    s = built(pcfg)
    st = state(pcfg)
    assert st["routes"]["u5"]["slot"] == "female_human" and st["routes"]["u5"]["source"] == "override"
    assert {x["id"]: x["name"] for x in s["slots"]}["female_human"] == "Women of the Expanse"


def test_rebuild_still_sees_lines_after_plan_reroutes_them(pcfg):
    path = pcfg.render / "jobs.jsonl"
    jobs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for j in jobs:
        if j["guid"] == "u1":
            j.update(speaker="Heinrix", routed_from="default_speaker", priority=1, voice_source="prompt_bank")
    path.write_text("\n".join(json.dumps(j) for j in jobs) + "\n", encoding="utf-8")
    assert built(pcfg)["total"] == 15


def test_a_rejected_match_decision_changes_the_route(pcfg):
    put(pcfg.data / "npc_profile/match_decisions.json", {"C1|a": "reject"})
    s = built(pcfg)
    assert s["destinations"]["speaker_bank"] == 0 and s["destinations"]["slot"] == 13


def test_missing_roster_is_a_clear_error_not_a_crash(pcfg):
    (pcfg.data / "npc_profile/roster_35b_all.json").unlink()      # test fixture file under tmp_path only
    with pytest.raises(ApiError) as e:
        pools.rebuild(pcfg, min_slot_lines=MIN)
    assert e.value.status == 404 and "roster" in e.value.message


def test_routes_page_filters_pages_and_caps_the_limit(pcfg):
    built(pcfg)
    page = pools.routes_page(pcfg, to="slot", slot="female_human")
    assert page["total"] == 3 and {i["guid"] for i in page["items"]} == {"u10", "u11", "u12"} and page["items"][0]["text"]
    assert pools.routes_page(pcfg, queued=True)["total"] == 3
    assert len(pools.routes_page(pcfg, limit=2)["items"]) == 2 and pools.routes_page(pcfg, offset=14, limit=5)["total"] == 15
    assert pools.routes_page(pcfg, speaker="Heinrix")["total"] == 2
    assert pools.routes_page(pcfg, limit=10_000)["limit"] == pools.MAX_PAGE


def test_queue_returns_every_evidence_item(pcfg):
    path = pcfg.data / "npc_profile/roster_35b_all.json"
    roster = json.loads(path.read_text(encoding="utf-8"))
    ev = [f"clue {i}" for i in range(8)]
    next(x for c in roster for x in c["roster"] if x["id"] == "q")["evidence"] = ev
    put(path, roster)
    built(pcfg)
    assert {g["key"]: g for g in pools.queue(pcfg)}[" C2|q"]["evidence"] == ev


def test_queue_groups_by_roster_entry_with_evidence_and_samples(pcfg):
    built(pcfg)
    q = pools.queue(pcfg)
    by = {g["key"]: g for g in q}
    assert by[" C2|q"]["lines"] == 2 and by[" C2|q"]["reasons"] == ["gender unknown"] and by[" C2|q"]["samples"]
    assert by[" C2|q"]["evidence"] == ["q said something"] and by[" C2|q"]["slot"] == "male_human"
    assert len(q) == 2 and q[0]["lines"] >= q[1]["lines"]


def test_override_by_entry_accepts_or_moves_and_clears_the_queue(pcfg):
    built(pcfg)
    assert pools.override(pcfg, {"entry": " C2|q"})["changed"] == 2              # accept the current destination
    assert pools.summary(pcfg)["queue_entries"] == 1 and state(pcfg)["routes"]["u13"]["source"] == "override"
    pools.override(pcfg, {"entry": " C2|q", "to": "slot", "slot": "female_human"})
    assert state(pcfg)["routes"]["u14"]["slot"] == "female_human"
    pools.override(pcfg, {"guids": ["u5"], "to": "narrator"})
    assert state(pcfg)["routes"]["u5"]["to"] == "narrator" and "slot" not in state(pcfg)["routes"]["u5"]
    pools.override(pcfg, {"guids": ["u6"], "to": "speaker", "speaker": "Heinrix"})
    r = state(pcfg)["routes"]["u6"]
    assert r["to"] == "speaker" and r["speaker"] == "Heinrix" and r["has_bank"] is True


@pytest.mark.parametrize("body", [
    {"guids": ["u5"], "to": "slot", "slot": "no_such_slot"},
    {"guids": ["u5"], "to": "speaker", "speaker": " "},
    {"guids": ["u5"], "to": "teleport"},
    {"guids": ["nope"]},
    {"entry": "none|none"},
])
def test_bad_overrides_are_400_and_write_nothing(pcfg, body):
    built(pcfg)
    before = pools.pools_path(pcfg).read_text(encoding="utf-8")
    with pytest.raises(ApiError) as e:
        pools.override(pcfg, body)
    assert e.value.status == 400 and pools.pools_path(pcfg).read_text(encoding="utf-8") == before


def test_merge_slot_moves_every_line_and_rename_validates(pcfg):
    built(pcfg)
    assert pools.merge_slot(pcfg, "female_human", "male_human") == {"changed": 3}
    st = state(pcfg)
    assert "female_human" not in st["slots"] and st["slots"]["male_human"]["lines"] == 11
    with pytest.raises(ApiError):
        pools.merge_slot(pcfg, "male_human", "male_human")
    with pytest.raises(ApiError):
        pools.rename_slot(pcfg, "male_human", "  ")


def test_spot_check_samples_unchecked_auto_lines_and_doubles_after_a_failure(pcfg, monkeypatch):
    monkeypatch.setattr(pools, "SPOT_CHECK_LINES", 2)
    built(pcfg)
    a = pools.spot_check_sample(pcfg, "male_human", seed=1)
    assert a["size"] == 2 and len(a["items"]) == 2 and a["remaining"] == 8
    assert pools.spot_check_sample(pcfg, "male_human", seed=1) == a              # same seed, same sample
    results = {a["items"][0]["guid"]: True, a["items"][1]["guid"]: False}
    assert pools.record_spot_check(pcfg, "male_human", results) == {"checked": 2, "wrong": 1}
    b = pools.spot_check_sample(pcfg, "male_human", seed=1)
    assert b["size"] == 4 and a["items"][0]["guid"] not in {i["guid"] for i in b["items"]}
    assert "spot-check failed" in state(pcfg)["routes"][a["items"][1]["guid"]]["reasons"]
    with pytest.raises(ApiError) as e:
        pools.spot_check_sample(pcfg, "nope")
    assert e.value.status == 404


def test_rebuild_keeps_spot_checked_marks(pcfg, monkeypatch):
    monkeypatch.setattr(pools, "SPOT_CHECK_LINES", 3)
    built(pcfg)
    a = pools.spot_check_sample(pcfg, "male_human", seed=2)
    pools.record_spot_check(pcfg, "male_human", {i["guid"]: True for i in a["items"]})
    built(pcfg)
    again = pools.spot_check_sample(pcfg, "male_human", seed=2)
    assert not ({i["guid"] for i in a["items"]} & {i["guid"] for i in again["items"]})


def test_rebuild_keeps_the_spot_check_failed_mark_and_queue_entry(pcfg, monkeypatch):
    monkeypatch.setattr(pools, "SPOT_CHECK_LINES", 2)
    built(pcfg)
    g = pools.spot_check_sample(pcfg, "male_human", seed=1)["items"][0]["guid"]
    pools.record_spot_check(pcfg, "male_human", {g: False})
    built(pcfg)
    r = state(pcfg)["routes"][g]
    assert r["checked"] and "spot-check failed" in r["reasons"]


def test_rebuild_keeps_a_merge(pcfg):
    built(pcfg)
    pools.merge_slot(pcfg, "female_human", "male_human")
    assert state(pcfg)["merged"] == {"female_human": "male_human"}
    built(pcfg)
    st = state(pcfg)
    assert "female_human" not in st["slots"] and st["slots"]["male_human"]["lines"] == 11
    assert all(r.get("slot") != "female_human" for r in st["routes"].values())


def test_an_old_pools_file_without_merged_still_loads(pcfg):
    built(pcfg)
    st = state(pcfg)
    st.pop("merged", None)
    pools.pools_path(pcfg).write_text(json.dumps(st), encoding="utf-8")
    assert built(pcfg)["total"] == 15


def test_a_merge_is_a_rename_so_matches_decisions_still_apply_afterwards(pcfg):
    built(pcfg)
    pools.merge_slot(pcfg, "male_human", "female_human")
    dec = pcfg.data / "npc_profile/match_decisions.json"
    put(dec, {"C1|a": "reject"})
    built(pcfg)
    st = state(pcfg)
    assert all(r["source"] == "auto" for r in st["routes"].values() if r["to"] == "slot")
    assert pools.summary(pcfg)["destinations"]["speaker_bank"] == 0
    put(dec, {})
    built(pcfg)
    assert pools.summary(pcfg)["destinations"]["speaker_bank"] > 0
    assert "male_human" not in state(pcfg)["slots"]


def test_spot_check_marks_are_not_copied_onto_a_line_that_changed_destination(pcfg, monkeypatch):
    monkeypatch.setattr(pools, "SPOT_CHECK_LINES", 2)
    built(pcfg)
    g = pools.spot_check_sample(pcfg, "male_human", seed=1)["items"][0]["guid"]
    pools.record_spot_check(pcfg, "male_human", {g: False})
    st = state(pcfg)
    st["routes"][g]["slot"] = "elsewhere"           # as if the rebuild now lands it in another slot
    pools.pools_path(pcfg).write_text(json.dumps(st), encoding="utf-8")
    built(pcfg)
    r = state(pcfg)["routes"][g]
    assert r["slot"] == "male_human" and not r.get("checked") and "spot-check failed" not in r["reasons"]
