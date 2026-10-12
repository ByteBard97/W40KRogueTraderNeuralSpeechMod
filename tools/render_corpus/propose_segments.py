#!/usr/bin/env python3
"""Propose speaker segments for cues whose text carries inline "Name:" labels (recordings, logs, shouted exchanges).

  python3 tools/render_corpus/propose_segments.py [--out data/npc_profile/segments_proposed.json]

Proposals are not used by any planner. Review them, then merge accepted ones with add_segments.py.
Segments stay one per label so segment_annotations.validate can check them against the cue; plan_annotated.py merges
adjacent segments of the same speaker when it builds render jobs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from segment_annotations import validate  # noqa: E402

NOT_SPEAKERS = {"Location", "Material", "Region", "Sector", "Note", "Warning", "Result", "Status", "Type", "Name", "Date", "Subject"}
DATA_WORDS = {"Location", "Region", "Material", "System", "Sector", "Category", "Subcategory", "Author", "Status", "Process"}
_TAG = re.compile(r"\{/?[a-z_]+(?:\|[^}]*)?\}")
_LABEL = re.compile(r"(?:(?<=[\"“\s])|^)([A-Z][\w' -]{0,28}):\s+(?=[A-Z\"“])")
NARRATOR = "narrator"


def _clean(piece: str) -> str:
    return piece.strip().strip("\"“”").strip()


def is_speaker_label(label: str) -> bool:
    """Record fields ("Koronus Expanse Location", "STATUS", "Subcategory") are not speakers."""
    if label in NOT_SPEAKERS or (len(label) > 2 and label.isupper()):
        return False
    return label.split()[-1] not in DATA_WORDS


def split_labelled(text: str) -> list[dict] | None:
    plain = re.sub(r"\s+", " ", _TAG.sub("", text)).strip()
    hits = [m for m in _LABEL.finditer(plain) if is_speaker_label(m.group(1))]
    if len({m.group(1) for m in hits}) < 2:
        return None
    segs = []
    lead = _clean(plain[:hits[0].start()])
    if re.search(r"[A-Za-z]", lead):
        segs.append({"speaker": NARRATOR, "kind": "narration", "text": lead})
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(plain)
        body = _clean(plain[m.end():end])
        if re.search(r"[A-Za-z]", body):
            segs.append({"speaker": m.group(1), "kind": "speech", "text": body})
    return segs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data/npc_profile/segments_proposed.json"))
    a = ap.parse_args()
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    out = {}
    for c in convs:
        for ln in c["lines"]:
            if ln.get("kind") != "cue" or not ln.get("text"):
                continue
            segs = split_labelled(ln["text"])
            if segs and not validate(ln["text"], {"segments": segs}):
                out[ln["text_key"]] = {"conversation": c["name"].strip(), "source": "inline-labels", "segments": segs}
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(out)} proposals -> {a.out}")


if __name__ == "__main__":
    main()
