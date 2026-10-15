import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_server import auto_cast_rules as R  # noqa: E402


def voice(slug, gender="male", age="adult", cls="middle", processing="natural", pitch="middle", species="human", accent="received (RP)", energy=None, quality="good", lines=100):
    labels = {"gender": gender, "age": age, "class": cls, "processing": processing, "pitch": pitch, "species": species, "accent": accent}
    if energy:
        labels["energy"] = energy
    return {"slug": slug, "name": slug, "lines": lines, "refs_quality": quality, "labels": labels}


def target(**kw):
    return {"key": kw.pop("key", "t"), "name": "T", "gender": "male", "species": "human", "age": None, "role": "", "description": "", "evidence": [], "fx": [], "lines": 10, **kw}


def test_class_comes_from_the_role_words():
    assert R.wanted_class("beggar") == 0
    assert R.wanted_class("ship enforcer") == 1
    assert R.wanted_class("") is None
    assert R.wanted_class("planetary governor") == 4
    assert R.wanted_class("tech-priest magos") == 3


def test_a_human_never_gets_a_processed_or_creature_voice_and_a_machine_always_gets_a_processed_one():
    voices = [voice("plain"), voice("robot", processing="processed", species="construct"), voice("orc", species="orc / goblin")]
    human = R.assign([target()], voices)["t"]
    assert human["bg3"] == "plain"
    machine = R.assign([target(species="machine")], voices)["t"]
    assert machine["bg3"] == "robot" and machine["processed"] is True


def test_a_servitor_is_processed_even_when_the_species_says_human():
    voices = [voice("plain"), voice("robot", processing="processed")]
    assert R.assign([target(role="servitor", fx=["machine"])], voices)["t"]["bg3"] == "robot"


def test_gender_is_a_hard_rule_but_unknown_gender_is_read_from_the_description():
    voices = [voice("man"), voice("woman", gender="female")]
    assert R.assign([target(gender="female")], voices)["t"]["bg3"] == "woman"
    guess = R.assign([target(gender=None, description="She speaks softly, her voice trembling.")], voices)["t"]
    assert guess["bg3"] == "woman"


def test_a_voice_in_between_genders_counts_for_either():
    voices = [voice("either", gender=["male", "female"])]
    assert R.assign([target(gender="female")], voices)["t"]["bg3"] == "either"


def test_age_class_and_pitch_pull_towards_the_closest_voice():
    voices = [voice("old_low", age="old", cls="low", pitch="low"), voice("young_high", age="youth", cls="high", pitch="high"), voice("mid")]
    young_noble = target(age="young", role="noble heir", description="a high, light voice")
    assert R.assign([young_noble], voices)["t"]["bg3"] == "young_high"
    old_beggar = target(age="old", role="beggar", description="a deep, rasping voice")
    assert R.assign([old_beggar], voices)["t"]["bg3"] == "old_low"


def test_manner_words_in_the_description_pick_matching_voices():
    voices = [voice("calm", energy=["calm"]), voice("menace", energy=["menacing"])]
    t = target(description="A cruel, menacing voice that threatens.")
    assert R.assign([t], voices)["t"]["bg3"] == "menace"


def test_voices_are_spread_out_and_the_biggest_character_chooses_first():
    voices = [voice("best"), voice("second", pitch="low")]
    ts = [target(key="small", lines=5), target(key="big", lines=500, description="a deep voice")]
    out = R.assign(ts, voices)
    assert out["big"]["bg3"] == "second" and out["small"]["bg3"] == "best"
    assert len({a["bg3"] for a in out.values()}) == 2


def test_groups_in_the_same_conversation_never_share_a_voice_while_others_remain():
    voices = [voice("a"), voice("b"), voice("c")]
    ts = [target(key=f"g{i}", conversation="Scene1", lines=10 - i) for i in range(3)]
    assert len({a["bg3"] for a in R.assign(ts, voices).values()}) == 3


def test_do_not_use_poor_references_and_taken_voices_are_handled():
    voices = [voice("bad", quality="poor"), voice("fine")]
    assert R.assign([target()], voices)["t"]["bg3"] == "fine"
    used = R.assign([target()], [voice("only")], prior_uses={"only": 3})["t"]
    assert used["bg3"] == "only"                       # reuse when nothing else fits, not an empty result


def test_a_result_explains_itself_and_offers_runners_up():
    voices = [voice("a"), voice("b", pitch="low"), voice("c", cls="low")]
    got = R.assign([target(role="beggar", description="a deep voice")], voices)["t"]
    assert got["reasons"] and all(isinstance(r, str) for r in got["reasons"])
    assert [x["bg3"] for x in got["alts"]] and got["bg3"] not in [x["bg3"] for x in got["alts"]]
    assert got["steps"] == R.DEFAULT_STEPS


def test_processed_voices_render_with_more_steps():
    got = R.assign([target(species="machine")], [voice("robot", processing="processed")])["t"]
    assert got["steps"] == R.PROCESSED_STEPS == 20


def test_missing_info_names_what_the_rules_cannot_work_out():
    assert R.missing_info(target(role="beggar")) == []
    assert R.missing_info(target(gender=None, role="beggar")) == ["gender"]
    assert R.missing_info(target(gender=None, role="beggar", description="She sighs.")) == []        # readable from the text
    assert R.missing_info(target(species=None, role="", description="")) == ["species", "role or description"]


def test_a_machine_needs_no_gender():
    assert R.missing_info(target(gender=None, species="machine", role="cogitator")) == []


def test_a_non_human_needs_no_gender_but_a_human_or_unknown_does():
    assert R.missing_info(target(gender=None, species="daemon", role="possessed beast")) == []
    assert R.missing_info(target(gender=None, species="human", role="guard")) == ["gender"]
    assert R.missing_info(target(gender=None, species=None, role="guard")) == ["gender", "species"]
