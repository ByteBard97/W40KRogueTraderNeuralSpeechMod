"""Hand-checked speaker segments for cues where more than one voice speaks (data/npc_profile/segments.json).

A cue maps to an ordered list of {speaker, kind, text, label?}. validate() proves the segments are an in-order copy of the cue text:
anything left over (quote marks, {n} tags, glossary links, "Name:" labels) may contain no words, so a segment list can never
drop or invent speech.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS = ROOT / "data/npc_profile/segments.json"
KINDS = ("speech", "narration")
_TAG = re.compile(r"\{/?[a-z_]+(?:\|[^}]*)?\}")   # {n} {/n} and glossary links {g|Encyclopedia:Vox} {/g}
_LABEL_TAIL = re.compile(r"([A-Z][\w' -]{0,28}):\s*$")   # a "Name:" label at the end of a gap, i.e. just before its segment
_WORD = re.compile(r"[A-Za-z0-9]")


def load(path: Path = ANNOTATIONS) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub("", text)).strip()


def _gaps(cue_text: str, segments: list[dict]) -> list[str] | None:
    rest, pos, gaps = _norm(cue_text), 0, []
    for s in segments:
        piece = _norm(s["text"])
        i = rest.find(piece, pos)
        if i < 0:
            return None
        gaps.append(rest[pos:i])
        pos = i + len(piece)
    gaps.append(rest[pos:])
    return gaps


def validate(cue_text: str, entry: dict) -> list[str]:
    segs = entry.get("segments") or []
    errors = []
    if len(segs) < 2:
        errors.append("needs at least two segments")
    for k, s in enumerate(segs):
        if s.get("kind") not in KINDS:
            errors.append(f"segment {k}: kind must be one of {KINDS}")
        if not s.get("speaker"):
            errors.append(f"segment {k}: missing speaker")
        if not (s.get("text") or "").strip():
            errors.append(f"segment {k}: empty text")
    if not errors and not any(s["kind"] == "speech" for s in segs):
        errors.append("needs at least one speech segment (an all-narration cue is not multi-speaker)")
    if errors:
        return errors
    gaps = _gaps(cue_text, segs)
    if gaps is None:
        return ["segments are not an in-order copy of the cue text"]
    for k, gap in enumerate(gaps):
        words = gap
        m = _LABEL_TAIL.search(gap) if k < len(segs) else None
        if m and m.group(1) in (segs[k].get("label"), segs[k]["speaker"]):   # only the segment's own label is excused
            words = gap[:m.start()]
        if _WORD.search(words):
            errors.append(f"cue text not covered by any segment: {words.strip()[:60]!r}")
    return errors
