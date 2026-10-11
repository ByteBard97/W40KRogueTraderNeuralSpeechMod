from __future__ import annotations

from collections import Counter

MIN_SLOT_LINES = 40
SLOT_PREFIX = "pool_"
KNOWN_GENDERS = ("male", "female")
AGE_SPLIT = ("old", "young")
OTHER_ID = "other"
DEFAULT_GENDER = "male"


# Voices that always exist, even when too few lines fit them to form a slot on their own.
STANDARD_SLOTS: dict[str, dict] = {
    "female_machine": {"id": "female_machine", "name": "Female machine", "speaker_key": SLOT_PREFIX + "female_machine",
                       "gender": "female", "species": "machine", "age": None, "lines": 0,
                       "description": "A woman, cyborg: a feminine voice with a modulated, vox-caster or mechanical timbre, "
                                      "British English accent, clear and measured."},
}


def _slot_record(slot_id: str, gender: str, species: str, age: str | None, lines: int) -> dict:
    if slot_id == OTHER_ID:
        name = "Other (mixed)"
    else:
        name = f"{gender.capitalize()} {species}" + (f", {age}" if age else "")
    return {"id": slot_id, "name": name, "speaker_key": SLOT_PREFIX + slot_id, "gender": gender, "species": species,
            "age": age, "lines": lines}


def assign_slots(routes: dict, min_lines: int = MIN_SLOT_LINES) -> dict[str, dict]:
    bound = [r for r in routes.values() if r["to"] == "slot" and "attr" in r]
    if not bound:
        return {}
    by_species: dict[str, Counter] = {}
    for r in bound:
        if r["attr"]["gender"] in KNOWN_GENDERS:
            by_species.setdefault(r["attr"]["species"], Counter())[r["attr"]["gender"]] += 1

    def gender_of(r: dict) -> str:
        g = r["attr"]["gender"]
        if g in KNOWN_GENDERS:
            return g
        seen = by_species.get(r["attr"]["species"])
        return seen.most_common(1)[0][0] if seen else DEFAULT_GENDER

    combos = Counter((gender_of(r), r["attr"]["species"]) for r in bound)
    ages = Counter((gender_of(r), r["attr"]["age"]) for r in bound if r["attr"]["species"] == "human")
    slots: dict[str, dict] = {}
    for r in bound:
        g, sp, age = gender_of(r), r["attr"]["species"], r["attr"]["age"]
        if combos[(g, sp)] < min_lines:
            sid, rec = OTHER_ID, ("any", "mixed", None)
        elif sp == "human" and age in AGE_SPLIT and ages[(g, age)] >= min_lines:
            sid, rec = f"{g}_human_{age}", (g, "human", age)
        else:
            sid, rec = f"{g}_{sp}", (g, sp, None)
        r["slot"] = sid
        if sid not in slots:
            slots[sid] = _slot_record(sid, *rec, lines=0)
        slots[sid]["lines"] += 1
    return slots
