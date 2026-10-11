import json

import pytest

from conftest import put, write_wav
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


def test_every_evidence_item_is_returned(pcfg):
    with_flagged(pcfg)
    path = pcfg.data / "npc_profile/roster_35b_all.json"
    roster = json.loads(path.read_text(encoding="utf-8"))
    ev = [f"clue {i}" for i in range(8)]
    next(x for x in roster[0]["roster"] if x["id"] == "a")["evidence"] = ev
    put(path, roster)
    assert {r["id"]: r for r in matches.rows(pcfg)}["C1|a"]["evidence"] == ev


def test_effective_defaults_clean_accepted_flagged_undecided(pcfg):
    with_flagged(pcfg)
    by = {r["id"]: r for r in matches.rows(pcfg)}
    assert matches.effective(by["C1|a"], {}) == "accept" and matches.effective(by["C1|w"], {}) == ""
    assert matches.effective(by["C1|a"], {"C1|a": "reject"}) == "reject"


def test_page_groups_filters_and_counts(pcfg):
    with_flagged(pcfg)
    p = matches.page(pcfg)
    assert p["total"] == 3 and {k: p["counts"][k] for k in ("flagged", "bank", "nobank", "undecided")} == {"flagged": 1, "bank": 1, "nobank": 1, "undecided": 1}
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


def test_counts_total_accepted_rejected_reviewed_and_unreviewed_filter(pcfg):
    with_flagged(pcfg)
    c = matches.page(pcfg)["counts"]
    assert (c["total"], c["accepted"], c["rejected"], c["reviewed"], c["unreviewed"], c["flagged_unreviewed"]) == (3, 0, 0, 0, 3, 1)
    matches.save(pcfg, "C1|a", "accept")
    matches.save(pcfg, "C1|w", "reject")
    p = matches.page(pcfg)
    c = p["counts"]
    assert (c["accepted"], c["rejected"], c["reviewed"], c["unreviewed"], c["flagged_unreviewed"]) == (1, 1, 2, 1, 0)
    assert [i["id"] for i in matches.page(pcfg, state="unreviewed")["items"]] == ["C1|b"]   # clean but never reviewed
    assert {i["id"] for i in matches.page(pcfg, state="reviewed")["items"]} == {"C1|a", "C1|w"}
    assert [i["id"] for i in matches.page(pcfg, state="reject")["items"]] == ["C1|w"]
    assert matches.page(pcfg, state="unreviewed")["counts"]["total"] == 3     # counts ignore the filters
    with pytest.raises(ApiError) as e:
        matches.page(pcfg, state="bogus")
    assert e.value.status == 400


def test_suggest_and_speaker_sample(pcfg):
    with_flagged(pcfg)
    by = {r["id"]: r for r in matches.rows(pcfg)}
    assert by["C1|w"]["suggest"] == "reject" and "ame tags Heinrix" in by["C1|w"]["suggest_reason"]
    assert by["C1|a"]["suggest"] == "accept" and by["C1|a"]["suggest_reason"] == ""
    assert by["C1|a"]["speaker_sample"] is None                       # Heinrix has a bank entry but no clip
    prompts = json.loads((pcfg.data / "voices/prompts/prompts.json").read_text(encoding="utf-8"))
    prompts["Heinrix"] = [{"rank": 1, "wav": "prompts/Heinrix/01.wav", "text": "t"}]
    put(pcfg.data / "voices/prompts/prompts.json", prompts)
    write_wav(pcfg.data / "voices/prompts/Heinrix/01.wav")
    by = {r["id"]: r for r in matches.rows(pcfg)}
    assert by["C1|a"]["speaker_sample"] == "data/voices/prompts/Heinrix/01.wav"
    assert by["C1|b"]["speaker_sample"] is None                       # no bank


def test_ambiguous_clean_bank_match_suggests_accept_with_reason():
    row = {"warning": None, "ambiguous_with": ["Idira the Insidious"], "speaker": "Idira", "has_bank": True}
    assert matches.suggestion(row) == ("accept", "Also matches Idira the Insidious. Accepting uses the Idira bank.")


def test_rows_are_cached_until_an_input_changes(pcfg, monkeypatch):
    calls = []
    real = matches._build_rows
    monkeypatch.setattr(matches, "_build_rows", lambda c: calls.append(1) or real(c))
    a = matches.rows(pcfg)
    assert matches.rows(pcfg) is a and len(calls) == 1
    matches.save(pcfg, "C1|a", "reject")                                # a decision is not a row input
    matches.page(pcfg)
    assert len(calls) == 1
    with_flagged(pcfg)
    assert len(matches.rows(pcfg)) == 3 and len(calls) == 2


def test_deferred_decisions_leave_pools_stale_until_flushed(pcfg):
    pools.rebuild(pcfg, min_slot_lines=3)
    assert matches.pools_stale(pcfg) is False
    r = matches.save(pcfg, "C1|a", "reject", rebuild=False)
    assert r == {"pools_rebuilt": False, "pools_stale": True}
    assert matches.pools_stale(pcfg) and matches.page(pcfg)["pools_stale"] is True
    assert pools.summary(pcfg)["destinations"]["speaker_bank"] == 2     # not rebuilt yet
    matches.save(pcfg, "C1|b", "accept", rebuild=False)                  # a burst
    out = matches.flush_pools(pcfg)
    assert out["pools_rebuilt"] is True and not matches.pools_stale(pcfg)
    assert pools.summary(pcfg)["destinations"]["speaker_bank"] == 0     # sees the rejection
    assert matches.flush_pools(pcfg) == {"pools_rebuilt": False, "pools_stale": False}


def test_debounced_flush_runs_once_after_a_burst(pcfg, monkeypatch):
    monkeypatch.setattr(matches, "REBUILD_DEBOUNCE_S", 0.05)
    pools.rebuild(pcfg, min_slot_lines=3)
    matches.save(pcfg, "C1|a", "reject", rebuild=False)
    matches.save(pcfg, "C1|b", "reject", rebuild=False)
    import time
    for _ in range(100):
        if not matches.pools_stale(pcfg):
            break
        time.sleep(0.05)
    assert not matches.pools_stale(pcfg) and pools.summary(pcfg)["destinations"]["speaker_bank"] == 0


def test_deferred_save_without_built_pools_is_not_stale(pcfg):
    assert matches.save(pcfg, "C1|a", "reject", rebuild=False) == {"pools_rebuilt": False}
    assert matches.pools_stale(pcfg) is False
