"""Who speaks the extracted game clips that the extractor (tools/extract_voice_lines.py) could not name.

The extractor names a clip from the game's speaker record, or by finding a companion's first name inside the event name. Events named by job
(Companions_Techpriest) or with another spelling (BNTRS_*_Pascal, *_Eogann) were left as "_unattributed": 1,446 of 5,188 clips. This module reads
them from the event's conversation name and, for conversations several people share, from who the narration names first. Nothing in
data/voices/catalog.json is changed: the result goes to data/voices/attribution.json and `catalog()` returns the catalog with it applied.
Each attributed clip carries its basis so it can be audited. Run: python3 -m studio_server.attribution
"""
from __future__ import annotations

import re
from collections import Counter

from .config import Config
from .jsonio import read_json, write_json_atomic

UNATTRIBUTED = "_unattributed"
# Conversations owned by one companion: the companion speaks the clip, whatever the narration says.
OWNED = [(r"^Companions_Techpriest", "Pasqal"), (r"^Companions_Smugler", "Jae"), (r"^Companions_Ranger", "Yrliet"), (r"^Companions_Navigator", "Cassia"),
         (r"^Companions_Psyker", "Idira"), (r"^Companions_Interrogator", "Heinrix"), (r"^Companions_Sororitas", "Argenta"), (r"^Companions_Seneschal", "Abelard"),
         (r"Pascal", "Pasqal"), (r"Eogann", "Eogunn")]
# Conversations named for a character but shared with others: the narration is read first, the conversation's character is the fallback.
SHARED = [(r"Theodora", "Theodora"), (r"Kunrad", "Kunrad Voigtvir"), (r"^Trazyn", "Trazyn, Lord of Histories"), (r"Dargonus", "Dargonus")]
# Characters with spoken lines who are not in the extractor's speaker list: how the narration spells them -> the name to use.
EXTRA_NAMES = {"Dargonus": "Dargonus", "Calcazar": "Xavier Calcazar"}
OWNED_BASIS, NARRATION_BASIS, SHARED_BASIS = "conversation name", "narration names the speaker", "conversation is named for the character"


def _subject(texts: list[dict], known: list[str]) -> str | None:
    text = (texts[0].get("text") if texts else "") or ""
    names = {**EXTRA_NAMES, **{k: k for k in known}}
    for spelled in sorted(names, key=len, reverse=True):
        if re.match(rf"\W*{re.escape(spelled)}\b", text):
            return names[spelled]
    return None


def attribute(event: str, texts: list[dict], known: list[str]) -> tuple[str, str] | None:
    """(speaker, basis) for one clip, or None when nothing says who speaks it."""
    for pat, who in OWNED:
        if re.search(pat, event):
            return who, OWNED_BASIS
    who = _subject(texts, known)
    if who:
        return who, NARRATION_BASIS
    for pat, owner in SHARED:
        if re.search(pat, event):
            return owner, SHARED_BASIS
    return None


def overlay_path(cfg: Config):
    return cfg.voices / "attribution.json"


def _raw(cfg: Config) -> dict:
    return read_json(cfg.voices / "catalog.json", {}) or {}


def build(cfg: Config) -> dict:
    """Attribute every unattributed clip that can be, and save the overlay."""
    cat = _raw(cfg)
    known = sorted({e["speaker"] for e in cat.values() if e["speaker"] != UNATTRIBUTED})
    out = {}
    for key, e in cat.items():
        if e["speaker"] != UNATTRIBUTED:
            continue
        got = attribute(e["event"], e.get("texts") or [], known)
        if got:
            out[key] = {"speaker": got[0], "basis": got[1]}
    write_json_atomic(overlay_path(cfg), out)
    left = sum(1 for e in cat.values() if e["speaker"] == UNATTRIBUTED) - len(out)
    return {"attributed": len(out), "left": left, "by_speaker": dict(Counter(v["speaker"] for v in out.values()).most_common()),
            "by_basis": dict(Counter(v["basis"] for v in out.values()))}


def catalog(cfg: Config) -> dict:
    """The extractor's catalog with the overlay applied to clips it left unattributed."""
    cat, over = _raw(cfg), read_json(overlay_path(cfg), {}) or {}
    return {k: ({**e, "speaker": over[k]["speaker"], "attribution": over[k]["basis"]} if e["speaker"] == UNATTRIBUTED and k in over else e) for k, e in cat.items()}


if __name__ == "__main__":
    import json
    print(json.dumps(build(Config()), indent=1))
