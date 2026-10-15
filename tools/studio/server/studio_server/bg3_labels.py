"""Labels for the BG3 voices, so a Rogue Trader character can be matched to a voice by filtering instead of auditioning hundreds.

The label set is data (SCHEMA), so the web pages draw their controls from it and adding a label is one entry here. The first five are the
ones the owner asked for and count toward "fully labelled"; the rest are optional extras. A label the owner has not set can still carry an
automatic guess (gender from the catalog, pitch from the median F0): the guess is shown dimmed and used by filters, but it does not count
as labelled. Labels live in data/studio/bg3_labels.json, one object per voice slug.
"""
from __future__ import annotations

from .config import Config
from .jsonio import STATE_LOCK, write_json_atomic
from .label_set import LabelSet

# Class and pitch are five steps, low to high; the two in between are for a voice that sits between two levels.
LEVELS = ["low", "low-middle", "middle", "middle-high", "high"]
BETWEEN = {frozenset(("low", "middle")): "low-middle", frozenset(("middle", "high")): "middle-high"}
LEVEL_KEYS = ("class", "pitch")
DO_NOT_USE = "do not use"

# key, label, kind ("single" | "multi" | "text" | "rating"), options, required, and allow_several: a voice in an in-between spot may carry
# more than one value of a "single" label (youth and adult); a filter then finds it under either. "multi" always allows several.
SCHEMA: list[dict] = [
    {"key": "gender", "allow_several": True, "label": "Gender", "kind": "single", "options": ["male", "female", "neuter"], "required": True},
    {"key": "age", "allow_several": True, "label": "Age", "kind": "single", "options": ["child", "youth", "adult", "old"], "required": True},
    {"key": "class", "label": "Class", "kind": "single", "options": LEVELS, "required": True},
    {"key": "processing", "allow_several": True, "label": "Processing", "kind": "single", "options": ["natural", "processed"], "required": True},
    {"key": "pitch", "label": "Pitch", "kind": "single", "options": LEVELS, "required": True},
    {"key": "accent", "allow_several": True, "label": "Accent", "kind": "single", "required": False,
     "options": ["received (RP)", "other British", "American", "Scots / Irish", "other"]},
    {"key": "species", "allow_several": True, "label": "Sounds like", "kind": "single", "required": False,
     "options": ["human", "elf", "dwarf", "halfling / gnome", "orc / goblin", "giant / ogre", "devil / demon", "undead", "construct", "creature"]},
    {"key": "texture", "label": "Texture", "kind": "multi", "required": False,
     "options": ["raspy", "gravelly", "smooth", "nasal", "breathy", "thin / reedy", "booming", "whispery", "shrill"]},
    {"key": "energy", "label": "Manner", "kind": "multi", "required": False,
     "options": ["calm", "gentle", "cheerful", "weary", "pompous", "cold", "menacing", "intense"]},
    {"key": "pace", "allow_several": True, "label": "Pace", "kind": "single", "options": ["slow", "medium", "fast"], "required": False},
    {"key": "rating", "label": "My rating", "kind": "rating", "options": ["1", "2", "3", "4", "5"], "required": False},
    {"key": "reserve", "label": "Use", "kind": "single", "options": ["free", "reserve for main characters", "do not use"], "required": False},
    {"key": "note", "label": "Note", "kind": "text", "options": [], "required": False},
]
LABELS = LabelSet(SCHEMA, "bg3_labels.json", done_when=lambda mine: mine.get("reserve") == DO_NOT_USE)
BY_KEY, REQUIRED = LABELS.by_key, LABELS.required
# Pitch bands by median F0 (Hz), per gender; a guess to save clicks, never counted as labelled.
PITCH_BANDS = {"male": (110.0, 140.0), "female": (190.0, 230.0)}
path, read_all, check, set_label, backup, progress = LABELS.path, LABELS.read_all, LABELS.check, LABELS.set_label, LABELS.backup, LABELS.progress


def is_complete(mine: dict) -> bool:
    """Fully labelled: the five required labels are set, or the voice is marked "do not use" (nothing more to say about it)."""
    return LABELS.is_complete(mine)


def auto(voice: dict) -> dict:
    """Guesses from what the catalog already knows."""
    out = {}
    g = voice.get("gender")
    if g in ("male", "female"):
        out["gender"] = g
        f0 = voice.get("median_f0_hz")
        if f0:
            lo, hi = PITCH_BANDS[g]
            out["pitch"] = "low" if f0 < lo else "high" if f0 > hi else "middle"
    return out


def effective(voice: dict, mine: dict) -> dict:
    return {**auto(voice), **{k: v for k, v in mine.items() if v not in (None, "", [])}}


def between_value(key: str, value) -> str | None:
    """The in-between step for two neighbouring levels picked together on class or pitch, else None."""
    if key not in LEVEL_KEYS or not isinstance(value, list):
        return None
    return BETWEEN.get(frozenset(value))


def migrate_between_values(cfg: Config) -> dict:
    """Turn the old two-button answers on class and pitch (low+middle, middle+high) into the in-between step.

    Backs the file up first. Anything that is not two neighbouring levels is left as it was and reported.
    """
    with STATE_LOCK:
        labels = read_all(cfg)
        changes, left = [], []
        for slug, mine in labels.items():
            for key in LEVEL_KEYS:
                if isinstance(mine.get(key), list):
                    new = between_value(key, mine[key])
                    (changes.append((mine, key, new)) if new else left.append(f"{slug}: {key}"))
        if not changes:
            return {"converted": 0, "left": left, "backup": None}
        saved = backup(cfg)
        for mine, key, new in changes:
            mine[key] = new
        write_json_atomic(path(cfg), labels)
    return {"converted": len(changes), "left": left, "backup": saved}
