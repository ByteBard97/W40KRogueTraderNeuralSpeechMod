"""Research on targets the casting rules know too little about: read what the game says about them and fill in what it makes plain.

For each target with missing information, pull every line it speaks (with the narration the game prints inside the cue, {n}...{/n}, which
describes the speaker), the player answers that lead into it, and the conversation's name and comment. Gendered words in that narration decide
a missing gender when one side clearly wins; species words fill a missing species. The dossier is kept in data/studio/auto_cast_research.json
so the browse page can show it, and auto_cast.run merges the facts it found. Anything still unclear stays on the research list.
"""
from __future__ import annotations

import json
import re

from . import auto_cast, speakers
from .config import Config
from .jsonio import STATE_LOCK, read_json, write_json_atomic

NARRATION = re.compile(r"\{n\}(.*?)\{/n\}", re.S)
TAGS = re.compile(r"\{[^}]*\}")
MALE = re.compile(r"\b(he|his|him|himself)\b", re.I)
FEMALE = re.compile(r"\b(she|her|hers|herself)\b", re.I)
MARGIN = 2                                  # one side must win by this many words before a gender is taken from the narration
SPECIES_WORDS = [("daemon", re.compile(r"daemon|warp[- ]?(?:beast|spawn)|possessed", re.I)),
                 ("machine", re.compile(r"servitor|servo-?skull|cogitator|machine spirit|automaton|augur", re.I)),
                 ("xenos_other", re.compile(r"xenos|alien|beast|abomination|monster", re.I)),
                 ("human", re.compile(r"\b(man|woman|guard|soldier|clerk|hand|keeper|reporter|operator|pirate|arbitrator)\b", re.I))]


def path(cfg: Config):
    return cfg.studio / "auto_cast_research.json"


def read(cfg: Config) -> dict:
    return read_json(path(cfg), {}) or {}


def _conversations(cfg: Config) -> dict[str, dict]:
    p = cfg.root / "data/conversations.enGB.json"
    rows = speakers._cached(p, lambda f: json.loads(f.read_text(encoding="utf-8"))) if p.is_file() else []
    return {c["name"].strip(): c for c in rows}


def dossier(cfg: Config, target: dict, convs: dict[str, dict] | None = None) -> dict:
    """Everything the game says around one target's lines."""
    conv = (convs if convs is not None else _conversations(cfg)).get((target.get("conversation") or "").strip())
    own = set(target.get("guids") or [])
    lines, narration = [], []
    if conv:
        by_guid = {l.get("guid"): l for l in conv["lines"]}
        for l in conv["lines"]:
            if l.get("text_key") not in own:
                continue
            raw = l.get("text") or ""
            narration += [n.strip() for n in NARRATION.findall(raw)]
            parent = by_guid.get(l.get("parent")) or {}
            lines.append({"say": TAGS.sub("", NARRATION.sub("", raw)).strip(), "after": TAGS.sub("", parent.get("text") or "").strip()})
    return {"conversation": (conv or {}).get("name"), "comment": (conv or {}).get("comment") or "", "lines": lines, "narration": narration,
            "nearby": nearby_pronouns(conv, mention_words(target))}


SENTENCE = re.compile(r"(?<=[.!?])\s+")
STOP = {"the", "and", "speaker", "voice", "npc", "unknown", "lines", "from", "with", "that"}


def mention_words(target: dict) -> list[str]:
    """Words that point at this character in other people's narration: the role, the label and the id, minus filler."""
    raw = " ".join([target.get("role") or "", target.get("name") or "", (target["key"].split("|")[-1]).replace("_", " ")])
    return sorted({w for w in re.findall(r"[a-z]{4,}", raw.lower()) if w not in STOP})


def nearby_pronouns(conv: dict | None, words: list[str]) -> str:
    """Narration sentences in the conversation that mention one of the words, each with the sentence after it."""
    if not conv or not words:
        return ""
    pat = re.compile(r"\b(?:" + "|".join(map(re.escape, words)) + r")", re.I)
    out = []
    for l in conv["lines"]:
        for block in NARRATION.findall(l.get("text") or ""):
            sents = SENTENCE.split(block)
            out += [" ".join(sents[i:i + 2]) for i, s in enumerate(sents) if pat.search(s)]
    return " ".join(out)


def read_dossier(d: dict) -> dict:
    """What the dossier makes plain: a gender when the narration's pronouns clearly lean one way, a species from its keywords."""
    text = " ".join([*d["narration"], d.get("nearby", "")])
    m, f = len(MALE.findall(text)), len(FEMALE.findall(text))
    out = {"pronouns": {"male": m, "female": f}}
    if m - f >= MARGIN:
        out["gender"] = "male"
    elif f - m >= MARGIN:
        out["gender"] = "female"
    blob = " ".join([text, d["comment"], *(l["say"] for l in d["lines"])])
    species = next((s for s, pat in SPECIES_WORDS if pat.search(blob)), None)
    if species:
        out["species"] = species
    return out


def research(cfg: Config) -> dict:
    """Build a dossier for every target still needing information and keep what it settles."""
    convs = _conversations(cfg)
    targets = {t["key"]: t for t in auto_cast.group_targets(cfg)}
    found: dict[str, dict] = {}
    for key, item in auto_cast.read(cfg)["items"].items():
        if item["status"] != "needs_info" and key not in read(cfg):
            continue
        t = targets.get(key)
        if t is None:
            continue
        d = dossier(cfg, t, convs)
        found[key] = {"dossier": d, "facts": read_dossier(d)}
    with STATE_LOCK:
        write_json_atomic(path(cfg), found)
    return {"researched": len(found), "settled": sum(1 for v in found.values() if "gender" in v["facts"] or "species" in v["facts"])}
