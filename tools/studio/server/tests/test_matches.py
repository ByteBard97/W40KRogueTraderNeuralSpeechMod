import json

import pytest

from conftest import put
from studio_server import matches, pools
from studio_server.errors import ApiError
from studio_server.jsonio import read_json


def with_flagged(cfg):
    """Add a roster entry whose gender contradicts the game's tag for Heinrix (5 lines, under the veto): flagged."""
    roster = json.loads((cfg.data / "npc_profile/roster_35b_all.json").read_text(encoding="utf-8"))
    roster[0]["roster"].append({"id": "w", "name": "Heinrix", "label": "W", "gender": "female", "species": "human", "age": "unknown",
                                "conf": {"gender": 0.95, "species": 0.95, "age": 0.9}, "evidence": ["w said"]})
    roster[0]["lines"].append({"n": 9, "key": "u1", "speaker": "w", "conf": {"speaker": 1.0}})
    put(cfg.data / "npc_profile/roster_35b_all.json", roster)


def test_rows_group_order_and_fields(pcfg):
    with_flagged(pcfg)
    rows = matches.rows(pcfg)
    assert [r["id"] for r in rows][:1] == ["C1|w"]                      # flagged first
    by = {r["id"]: r for r in rows}
    assert set(by) == {"C1|a", "C1|b", "C1|w"}
    assert by["C1|w"]["flagged"] and by["C1|w"]["warning"]
    assert by["C1|a"]["has_bank"] is True and by["C1|b"]["has_bank"] is False
    assert by["C1|a"]["speaker"] == "Heinrix" and by["C1|a"]["lines"] == 2 and by["C1|a"]["samples"]
    assert by["C1|a"]["evidence"] == ["a said something"]


def test_effective_defaults_clean_accepted_flagged_undecided(pcfg):
    with_flagged(pcfg)
    by = {r["id"]: r for r in matches.rows(pcfg)}
    assert matches.effective(by["C1|a"], {}) == "accept" and matches.effective(by["C1|w"], {}) == ""
    assert matches.effective(by["C1|a"], {"C1|a": "reject"}) == "reject"


def test_page_groups_filters_and_counts(pcfg):
    with_flagged(pcfg)
    p = matches.page(pcfg)
    assert p["total"] == 3 and p["counts"] == {"flagged": 1, "bank": 1, "nobank": 1, "undecided": 1}
    assert [i["id"] for i in matches.page(pcfg, group="bank")["items"]] == ["C1|a"]
    assert [i["id"] for i in matches.page(pcfg, speaker="terv")["items"]] == ["C1|b"]
    assert [i["id"] for i in matches.page(pcfg, state="undecided")["items"]] == ["C1|w"]
    assert [i["id"] for i in matches.page(pcfg, q="unnamed line 3")["items"]] == ["C1|b"]
    assert len(matches.page(pcfg, limit=1)["items"]) == 1 and matches.page(pcfg, limit=10_000)["limit"] == matches.MAX_PAGE
    assert matches.page(pcfg, offset=2)["items"][0]["id"] == "C1|b"


def test_save_writes_clears_and_keeps_the_old_format(pcfg):
    put(pcfg.data / "npc_profile/match_decisions.json", {"Other|x": "accept"})
    assert matches.save(pcfg, "C1|a", "reject")["pools_rebuilt"] is False
    path = pcfg.data / "npc_profile/match_decisions.json"
    assert read_json(path, {}) == {"C1|a": "reject", "Other|x": "accept"}
    assert json.loads(path.read_text(encoding="utf-8")) == dict(sorted(read_json(path, {}).items()))
    matches.save(pcfg, "C1|a", "")
    assert read_json(path, {}) == {"Other|x": "accept"}


@pytest.mark.parametrize("rid,value,status", [("C1|a", "maybe", 400), ("nope|nope", "accept", 404)])
def test_save_rejects_bad_input_and_writes_nothing(pcfg, rid, value, status):
    with pytest.raises(ApiError) as e:
        matches.save(pcfg, rid, value)
    assert e.value.status == status and not (pcfg.data / "npc_profile/match_decisions.json").exists()


def test_a_saved_decision_rebuilds_the_pools_when_they_exist(pcfg):
    pools.rebuild(pcfg, min_slot_lines=3)
    assert pools.summary(pcfg)["destinations"]["speaker_bank"] == 2
    r = matches.save(pcfg, "C1|a", "reject")
    assert r["pools_rebuilt"] is True and "queue_entries" in r
    assert pools.summary(pcfg)["destinations"]["speaker_bank"] == 0     # Heinrix's lines fell through to slots


def test_missing_roster_is_a_clear_404(pcfg):
    (pcfg.data / "npc_profile/roster_35b_all.json").unlink()
    with pytest.raises(ApiError) as e:
        matches.rows(pcfg)
    assert e.value.status == 404


def test_samples_come_from_all_conversation_lines_cut_at_600(pcfg):
    conv = json.loads((pcfg.data / "conversations.enGB.json").read_text(encoding="utf-8"))
    conv[0]["lines"][0].update(text_key="u1", text="x" * 700)
    conv[0]["lines"][1].update(text_key="not_unnamed", text="A named-speaker line.")
    put(pcfg.data / "conversations.enGB.json", conv)
    roster = json.loads((pcfg.data / "npc_profile/roster_35b_all.json").read_text(encoding="utf-8"))
    roster[0]["lines"].append({"n": 20, "key": "not_unnamed", "speaker": "a", "conf": {"speaker": 1.0}})
    put(pcfg.data / "npc_profile/roster_35b_all.json", roster)
    a = next(r for r in matches.rows(pcfg) if r["id"] == "C1|a")
    assert a["samples"][0] == "x" * matches.SAMPLE_CHARS and "A named-speaker line." in a["samples"]
