import pytest

from studio_server.pools_routing import build_known, entry_key, route_lines

KNOWN = {
    "Heinrix": {"lines": 40, "gender": "male", "has_bank": True, "tokens": {"heinrix"}},
    "Tervantias the Archmachinator": {"lines": 40, "gender": "male", "has_bank": False,
                                      "tokens": {"tervantias", "archmachinator"}},
}


def entry(rid, name=None, gender="male", species="human", age="unknown", conf=None):
    return {"id": rid, "name": name, "label": rid, "gender": gender, "species": species, "age": age,
            "conf": conf or {"gender": 0.95, "species": 0.95, "age": 0.9}, "evidence": []}


def conv(name, entries, lines):
    return {"conversation": name, "roster": entries,
            "lines": [{"n": i, "key": k, "speaker": s, "conf": {"speaker": c}} for i, (k, s, c) in enumerate(lines)]}


def route(roster, guids, decisions=None, threshold=0.8):
    return route_lines(set(guids), roster, KNOWN, decisions or {}, threshold)


def test_known_speaker_with_bank_and_without_bank():
    r = route([conv("C", [entry("a", "Heinrix"), entry("b", "Tervantias")], [("g1", "a", 1.0), ("g2", "b", 1.0)])], ["g1", "g2"])
    assert r["g1"]["to"] == "speaker" and r["g1"]["speaker"] == "Heinrix" and r["g1"]["has_bank"] is True
    assert r["g2"]["speaker"] == "Tervantias the Archmachinator" and r["g2"]["has_bank"] is False
    assert r["g1"]["entry"] == "C|a" and r["g1"]["reasons"] == [] and r["g1"]["source"] == "auto"


def test_narrator_lines_route_to_the_narrator():
    r = route([conv("C", [], [("g1", "NARRATOR", 1.0)])], ["g1"])
    assert r["g1"]["to"] == "narrator" and r["g1"]["entry"] is None and r["g1"]["reasons"] == []


def test_unknown_character_goes_to_a_slot_with_its_attributes():
    r = route([conv("C", [entry("m", gender="female", species="eldar", age="old")], [("g1", "m", 1.0)])], ["g1"])
    assert r["g1"]["to"] == "slot" and r["g1"]["attr"] == {"gender": "female", "species": "eldar", "age": "old"}
    assert r["g1"]["reasons"] == []


def test_a_rejected_match_falls_through_to_a_slot_and_an_accepted_one_clears_ambiguity():
    roster = [conv("C", [entry("a", "Heinrix")], [("g1", "a", 1.0)])]
    rejected = route(roster, ["g1"], {entry_key("C", "a"): "reject"})
    assert rejected["g1"]["to"] == "slot"
    known = {**KNOWN, "Heinrix Two": {"lines": 3, "gender": "male", "has_bank": False, "tokens": {"heinrix", "two"}}}
    amb = route_lines({"g1"}, roster, known, {}, 0.8)
    assert amb["g1"]["to"] == "speaker"
    accepted = route_lines({"g1"}, roster, known, {entry_key("C", "a"): "accept"}, 0.8)
    assert accepted["g1"]["reasons"] == []


@pytest.mark.parametrize("ent,line_conf,expected", [
    (entry("m", gender="unknown"), 1.0, ["gender unknown"]),
    (entry("m", conf={"gender": 0.5, "species": 0.95, "age": 0.9}), 1.0, ["gender low confidence"]),
    (entry("m", species="unknown"), 1.0, ["species unknown"]),
    (entry("m", conf={"gender": 0.95, "species": 0.4, "age": 0.9}), 1.0, ["species low confidence"]),
    (entry("m"), 0.5, ["line attribution"]),
    (entry("m", age="unknown", conf={"gender": 0.95, "species": 0.95, "age": 0.1}), 1.0, []),   # unknown age is not a review reason
])
def test_queue_reasons_use_only_the_voice_defining_axes(ent, line_conf, expected):
    r = route([conv("C", [ent], [("g1", "m", line_conf)])], ["g1"])
    assert r["g1"]["reasons"] == expected


def test_a_line_with_no_roster_entry_goes_to_a_human_slot_and_the_queue():
    r = route([conv("C", [], [("g1", "ghost", 1.0)])], ["g1"])
    assert r["g1"]["to"] == "slot" and r["g1"]["reasons"] == ["no roster entry"]
    assert r["g1"]["attr"]["species"] == "human"


def test_guids_missing_from_the_roster_still_get_a_queued_route():
    r = route([], ["lost"])
    assert r["lost"]["to"] == "slot" and r["lost"]["reasons"] == ["not in roster"]


def test_only_requested_guids_are_routed_and_first_conversation_wins():
    roster = [conv("A", [entry("m")], [("g1", "m", 1.0), ("other", "m", 1.0)]), conv("B", [entry("x", "Heinrix")], [("g1", "x", 1.0)])]
    r = route(roster, ["g1"])
    assert set(r) == {"g1"} and r["g1"]["to"] == "slot"


def test_build_known_is_reexported():
    assert callable(build_known)
