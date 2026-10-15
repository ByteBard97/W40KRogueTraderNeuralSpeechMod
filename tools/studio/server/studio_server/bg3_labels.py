"""Labels for the BG3 voices, so a Rogue Trader character can be matched to a voice by filtering instead of auditioning hundreds.

The label set is data (SCHEMA), so the web pages draw their controls from it and adding a label is one entry here. The first five are the
ones the owner asked for and count toward "fully labelled"; the rest are optional extras. A label the owner has not set can still carry an
automatic guess (gender from the catalog, pitch from the median F0): the guess is shown dimmed and used by filters, but it does not count
as labelled. Labels live in data/studio/bg3_labels.json, one object per voice slug.
"""
from __future__ import annotations

import time
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

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
BY_KEY = {d["key"]: d for d in SCHEMA}
REQUIRED = [d["key"] for d in SCHEMA if d["required"]]
# Pitch bands by median F0 (Hz), per gender; a guess to save clicks, never counted as labelled.
PITCH_BANDS = {"male": (110.0, 140.0), "female": (190.0, 230.0)}
MAX_TEXT = 500


def path(cfg: Config) -> Path:
    return cfg.studio / "bg3_labels.json"


def read_all(cfg: Config) -> dict[str, dict]:
    return read_json(path(cfg), {})


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


def is_complete(mine: dict) -> bool:
    """Fully labelled: the five required labels are set, or the voice is marked "do not use" (nothing more to say about it)."""
    if mine.get("reserve") == DO_NOT_USE:
        return True
    return all(mine.get(k) not in (None, "", []) for k in REQUIRED)


def check(key: str, value) -> object:
    d = BY_KEY.get(key)
    if d is None:
        raise ApiError(400, f"unknown label {key!r}")
    if value in (None, "", []):
        return None
    if d["kind"] == "text":
        return str(value)[:MAX_TEXT]
    several = d["kind"] == "multi" or d.get("allow_several")
    if isinstance(value, list) and not several:
        raise ApiError(400, f"{key} takes one value")
    vals = value if isinstance(value, list) else [value]
    bad = [v for v in vals if v not in d["options"]]
    if bad:
        raise ApiError(400, f"{key} has no option {bad[0]!r}")
    ordered = [o for o in d["options"] if o in vals]
    return ordered if d["kind"] == "multi" or len(ordered) > 1 else ordered[0]      # one value stays a plain string


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


def set_label(cfg: Config, slug: str, key: str, value) -> dict:
    """Set (or, with an empty value, clear) one label of one voice. Returns that voice's labels."""
    clean = check(key, value)
    with STATE_LOCK:
        labels = read_all(cfg)
        mine = labels.setdefault(slug, {})
        if clean is None:
            mine.pop(key, None)
        else:
            mine[key] = clean
        if not mine:
            labels.pop(slug, None)
        write_json_atomic(path(cfg), labels)
        _rolling_backup(cfg)
    return labels.get(slug, {})


BACKUP_EVERY_S = 1800


def _rolling_backup(cfg: Config) -> None:
    """Hours of labelling are worth a copy: keep one at least every half hour while labels are being set."""
    mine = list(path(cfg).parent.glob("bg3_labels.*.bak.json"))
    if not mine or time.time() - max(f.stat().st_mtime for f in mine) > BACKUP_EVERY_S:
        backup(cfg)


def backup(cfg: Config) -> str | None:
    """Timestamped copy of the labels file."""
    p = path(cfg)
    if not p.is_file():
        return None
    dst = p.with_name(f"bg3_labels.{time.strftime('%Y%m%d-%H%M%S')}.bak.json")
    dst.write_bytes(p.read_bytes())
    return dst.name


def progress(cfg: Config, voices: list[dict]) -> dict:
    labels = read_all(cfg)
    done = sum(1 for v in voices if is_complete(labels.get(v["slug"], {})))
    return {"total": len(voices), "complete": done, "started": sum(1 for v in voices if labels.get(v["slug"]))}
