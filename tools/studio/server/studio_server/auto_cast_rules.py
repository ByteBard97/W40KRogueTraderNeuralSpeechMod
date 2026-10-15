"""Automatic casting rules: which BG3 voice suits a Rogue Trader character who has no voice of their own yet.

Pure functions, no files. A *target* is a dict (key, name, gender, species, age, role, description, evidence, fx, lines, optional conversation);
a *voice* is a dict (slug, name, lines, refs_quality, labels) where labels are the owner's BG3 labels. Gender, processing and "human-sounding"
are hard rules; age, class, pitch, manner, accent and species are scores; a voice already used counts against itself so the choices spread out.
"""
from __future__ import annotations

import re

DEFAULT_STEPS = 15
PROCESSED_STEPS = 20                      # a processed voice needs more denoising steps to clone cleanly
ALTERNATIVES = 3
LEVELS = ["low", "low-middle", "middle", "middle-high", "high"]

W_AGE_MATCH, W_AGE_MISS = 1.0, -1.5
W_ADULT_DEFAULT = 0.3
W_CLASS_STEP = -0.8
W_PITCH_STEP = -0.6
W_MANNER, MANNER_CAP = 0.7, 2
W_ACCENT = 0.5
W_ACCENT_REGION = 0.8
W_SPECIES = 1.0
W_QUALITY_GOOD = 0.4
W_REUSE = -1.2
W_SAME_SCENE = -6.0

CLASS_WORDS: list[tuple[int, str]] = [
    (0, r"beggar|servant|servitor|slave|thug|cutthroat|gangster|ruffian|miner|prisoner|scaveng\w*|cultist|rebel|urchin|drunk|smuggler|pirate|mutant|vagrant|refugee|pickpocket|hungry|crippled|outcast|bandit|raider"),
    (4, r"governor|lord|lady|prince|noble|magistrate|ambassador|envoy|admiral|regent|prefect|cardinal|inquisitor|aristocrat|patrician|heir|queen|king|emperor|archon|grand|high"),
    (3, r"magos|tech-?priest|priest|preacher|confessor|secretary|scholar|doctor|medicus|judge|advocate|merchant|factor|representative|steward|genetor|navigator"),
    (1, r"guard|soldier|sergeant|enforcer|crew\w*|worker|technician|sailor|trooper|clerk|scribe|officer|warrior|fighter|security|deckhand|labou?rer|janitor|cook|mechanic|pilgrim|marine"),
]
PITCH_LOW = re.compile(r"\b(deep|gravel\w*|bass|boom\w*|rumbl\w*|gruff|growl\w*)\b", re.I)
PITCH_HIGH = re.compile(r"\b(high[- ]pitched|high voice|high,|shrill|reedy|squeak\w*|girlish|piping)", re.I)
MANNER_WORDS = {
    "menacing": r"menac\w*|threaten\w*|cruel|sinister|sadistic", "cheerful": r"cheerful|flippant|jok\w*|playful|bubbly",
    "weary": r"weary|tired|exhausted|resigned", "pompous": r"pompous|arrogant|haughty|imperious|commanding|self-important",
    "cold": r"\bcold\b|calculating|detached|clinical", "calm": r"\bcalm\b|measured|composed|steady",
    "gentle": r"gentle|soft-spoken|kind|tender", "intense": r"intense|angry|fierce|passionate|furious|desperate"}
SPECIES_LIKES = {"eldar": {"elf"}, "machine": {"construct"}, "necron": {"construct", "undead"}, "daemon": {"devil / demon"},
                 "mutant": {"creature", "orc / goblin"}, "xenos_other": {"creature"}}
MACHINE_SPECIES = {"machine", "necron"}
MACHINE_ROLE = re.compile(r"servitor|servo-?skull|automaton|cogitator|machine spirit", re.I)
FEMALE_WORDS = re.compile(r"\b(she|her|hers|herself|woman|lady|girl|mother|daughter)\b", re.I)
MALE_WORDS = re.compile(r"\b(he|his|him|himself|man|lord|boy|father|son)\b", re.I)
REGION_WORDS = re.compile(r"space wolves?|fenris\w*|viking|northern", re.I)
AGE_WORDS = {"young": "youth", "child": "child", "old": "old", "adult": "adult"}
OLD_HINT = re.compile(r"elderly|aged|ancient|frail", re.I)


def _vals(v: dict, key: str) -> list[str]:
    x = v["labels"].get(key)
    return [] if x in (None, "") else (x if isinstance(x, list) else [x])


def wanted_class(role: str) -> int | None:
    """Social class from the role words, 0 low to 4 high; None when the role says nothing."""
    for idx, pat in CLASS_WORDS:
        if re.search(rf"\b(?:{pat})\b", role or "", re.I):
            return idx
    return None


def _text(t: dict) -> str:
    return " ".join([t.get("role") or "", t.get("description") or "", *(t.get("evidence") or [])])


def wanted_gender(t: dict) -> str | None:
    if t.get("gender") in ("male", "female"):
        return t["gender"]
    text = _text(t)
    f, m = len(FEMALE_WORDS.findall(text)), len(MALE_WORDS.findall(text))
    return "female" if f > m else "male" if m > f else None


def missing_info(t: dict) -> list[str]:
    """What is not known about a target that the rules need: a gender (stated or readable from the text), a species, and a role or description."""
    out = []
    if wanted_gender(t) is None and t.get("species") in (None, "", "unknown", "human"):          # a machine, daemon or beast voice needs no gender
        out.append("gender")
    if t.get("species") in (None, "", "unknown"):
        out.append("species")
    if not (t.get("role") or t.get("description")):
        out.append("role or description")
    return out


def needs_processed(t: dict) -> bool:
    return t.get("species") in MACHINE_SPECIES or "machine" in (t.get("fx") or []) or bool(MACHINE_ROLE.search(t.get("role") or ""))


def wanted_age(t: dict) -> str | None:
    a = AGE_WORDS.get(t.get("age") or "")
    return a or ("old" if OLD_HINT.search(_text(t)) else None)


def _distance(have: list[str], want: int) -> int | None:
    idx = [LEVELS.index(x) for x in have if x in LEVELS]
    return min(abs(i - want) for i in idx) if idx else None


def _wanted_pitch(t: dict) -> int | None:
    text = t.get("description") or ""
    return 0 if PITCH_LOW.search(text) else 4 if PITCH_HIGH.search(text) else None


def _allowed(t: dict, v: dict, gender: str | None, processed: bool, relax_processing: bool) -> bool:
    if v.get("refs_quality") == "poor" or (v.get("non_human") and t.get("species") == "human"):
        return False
    genders = _vals(v, "gender") or ([v["gender"]] if v.get("gender") in ("male", "female") else [])
    if gender and genders and gender not in genders and not (processed and "neuter" in genders):
        return False
    proc = _vals(v, "processing")
    if processed and not relax_processing and proc and "processed" not in proc:
        return False
    if not processed and proc == ["processed"]:
        return False
    sp = _vals(v, "species")
    return not (t.get("species") == "human" and sp and "human" not in sp)


def _score(t: dict, v: dict, uses: dict[str, int], scene: set[str]) -> tuple[float, list[str]]:
    s, why = 0.0, []
    age, ages = wanted_age(t), _vals(v, "age")
    if age and ages:
        hit = age in ages
        s += W_AGE_MATCH if hit else W_AGE_MISS
        why.append(f"age {age}" if hit else f"age {age} (voice is {'/'.join(ages)})")
    elif ages and "adult" in ages:
        s += W_ADULT_DEFAULT
    cls = wanted_class(t.get("role") or "")
    if cls is not None and (d := _distance(_vals(v, "class"), cls)) is not None:
        s += W_CLASS_STEP * d
        why.append(f"{LEVELS[cls]} class" + ("" if d == 0 else f" (voice is {d} step{'s' if d > 1 else ''} off)"))
    pitch = _wanted_pitch(t)
    if pitch is not None and (d := _distance(_vals(v, "pitch"), pitch)) is not None:
        s += W_PITCH_STEP * d
        why.append(f"{LEVELS[pitch]} pitch" + ("" if d == 0 else f" ({d} off)"))
    manner = [m for m, pat in MANNER_WORDS.items() if re.search(pat, t.get("description") or "", re.I) and m in _vals(v, "energy")][:MANNER_CAP]
    s += W_MANNER * len(manner)
    why += [f"manner {m}" for m in manner]
    accents = _vals(v, "accent")
    region = REGION_WORDS.search(_text(t))
    if region and "Scots / Irish" in accents:
        s += W_ACCENT_REGION
        why.append("northern accent")
    elif cls is not None and ((cls >= 3 and "received (RP)" in accents) or (cls <= 1 and "other British" in accents)):
        s += W_ACCENT
        why.append("accent fits the class")
    likes = SPECIES_LIKES.get(t.get("species") or "", set())
    if likes & set(_vals(v, "species")):
        s += W_SPECIES
        why.append(f"sounds like {sorted(likes & set(_vals(v, 'species')))[0]}")
    if v.get("refs_quality") == "good":
        s += W_QUALITY_GOOD
    n = uses.get(v["slug"], 0)
    if n:
        s += W_REUSE * n
        why.append(f"already used {n}x")
    else:
        why.append("unused")
    if v["slug"] in scene:
        s += W_SAME_SCENE
        why.append("same scene as another group with this voice")
    return s, why


def assign(targets: list[dict], voices: list[dict], prior_uses: dict[str, int] | None = None) -> dict[str, dict]:
    """A voice for every target, the one with the most lines choosing first. Targets nobody fits are left out."""
    uses = dict(prior_uses or {})
    scene: dict[str, set[str]] = {}
    out: dict[str, dict] = {}
    for t in sorted(targets, key=lambda x: (-x.get("lines", 0), x["key"])):
        gender, processed = wanted_gender(t), needs_processed(t)
        pool = []
        for relax in (False, True):
            pool = [v for v in voices if _allowed(t, v, gender, processed, relax)]
            if pool or not processed:
                break
        if not pool:
            continue
        taken = scene.setdefault(t.get("conversation") or t["key"], set())
        ranked = sorted(((*_score(t, v, uses, taken if t.get("conversation") else set()), v) for v in pool),
                        key=lambda r: (-r[0], -v_lines(r[2]), r[2]["slug"]))
        top_score, why, best = ranked[0]
        if gender:
            why.insert(0, gender)
        is_proc = "processed" in _vals(best, "processing")
        out[t["key"]] = {"bg3": best["slug"], "score": round(top_score, 2), "reasons": why, "processed": is_proc,
                         "steps": PROCESSED_STEPS if is_proc else DEFAULT_STEPS,
                         "alts": [{"bg3": r[2]["slug"], "score": round(r[0], 2)} for r in ranked[1:1 + ALTERNATIVES]]}
        uses[best["slug"]] = uses.get(best["slug"], 0) + 1
        taken.add(best["slug"])
    return out


def v_lines(v: dict) -> int:
    return v.get("lines", 0)
