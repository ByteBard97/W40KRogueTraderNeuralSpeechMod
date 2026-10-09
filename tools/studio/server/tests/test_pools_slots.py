from studio_server.pools_slots import assign_slots


def r(gender="male", species="human", age="unknown"):
    return {"to": "slot", "attr": {"gender": gender, "species": species, "age": age}, "entry": "C|x",
            "confidence": 1.0, "reasons": [], "source": "auto"}


def many(n, **kw):
    return {f"g{kw.get('gender','m')}{kw.get('species','h')}{kw.get('age','a')}{i}": r(**kw) for i in range(n)}


def test_basic_slots_names_keys_and_counts():
    routes = {**many(5, gender="male"), **many(4, gender="female")}
    slots = assign_slots(routes, min_lines=3)
    assert set(slots) == {"male_human", "female_human"}
    assert slots["male_human"]["lines"] == 5 and slots["male_human"]["speaker_key"] == "pool_male_human"
    assert slots["male_human"]["name"] == "Male human"
    assert all(v["slot"] in slots for v in routes.values())


def test_unknown_gender_joins_the_majority_gender_of_its_species():
    routes = {**many(5, gender="male"), **many(2, gender="female"), **many(3, gender="unknown")}
    slots = assign_slots(routes, min_lines=2)
    assert slots["male_human"]["lines"] == 8 and slots["female_human"]["lines"] == 2


def test_unknown_gender_with_no_known_gender_defaults_to_male():
    slots = assign_slots(many(3, gender="unknown", species="machine"), min_lines=2)
    assert set(slots) == {"male_machine"}


def test_small_combinations_merge_into_other():
    routes = {**many(6, gender="male"), **many(2, gender="male", species="tyranid"), **many(1, gender="female", species="daemon")}
    slots = assign_slots(routes, min_lines=3)
    assert set(slots) == {"male_human", "other"}
    assert slots["other"]["lines"] == 3 and slots["other"]["name"] == "Other (mixed)" and slots["other"]["gender"] == "any"


def test_human_age_groups_split_only_when_big_enough():
    routes = {**many(5, gender="male"), **many(4, gender="male", age="old"), **many(1, gender="male", age="young")}
    slots = assign_slots(routes, min_lines=3)
    assert set(slots) == {"male_human", "male_human_old"}
    assert slots["male_human_old"]["lines"] == 4 and slots["male_human"]["lines"] == 6
    assert slots["male_human_old"]["name"] == "Male human, old" and slots["male_human_old"]["age"] == "old"


def test_non_slot_routes_are_ignored_and_empty_input_is_fine():
    routes = {"a": {"to": "narrator", "entry": None, "confidence": 1.0, "reasons": [], "source": "auto"}}
    assert assign_slots(routes) == {} and "slot" not in routes["a"]
    assert assign_slots({}) == {}
