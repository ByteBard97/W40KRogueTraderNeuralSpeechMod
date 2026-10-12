#!/usr/bin/env python3
"""Validate a segment entry against the cue's text and merge it into data/npc_profile/segments.json.

  add_segments.py GUID --file entry.json          (entry.json: {"segments": [...], "source": "..."})
  add_segments.py GUID --from-proposed            (take it from segments_proposed.json)

The previous segments.json is copied to segments.json.bak first. An invalid entry is refused and nothing is written.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from segment_annotations import ANNOTATIONS, load, validate  # noqa: E402


def cue_text(guid: str) -> str | None:
    for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8")):
        for ln in c["lines"]:
            if ln.get("text_key") == guid and ln.get("text"):
                return ln["text"]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("guid")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file")
    src.add_argument("--from-proposed", action="store_true")
    a = ap.parse_args()
    if a.from_proposed:
        entry = json.loads((ROOT / "data/npc_profile/segments_proposed.json").read_text(encoding="utf-8"))[a.guid]
    else:
        entry = json.loads(Path(a.file).read_text(encoding="utf-8"))
    text = cue_text(a.guid)
    if text is None:
        sys.exit(f"no cue with text_key {a.guid}")
    errors = validate(text, entry)
    if errors:
        sys.exit("refused: " + "; ".join(errors))
    current = load()
    if ANNOTATIONS.is_file():
        shutil.copyfile(ANNOTATIONS, ANNOTATIONS.with_suffix(".json.bak"))
    current[a.guid] = {k: entry[k] for k in ("segments", "source", "conversation") if k in entry}
    ANNOTATIONS.parent.mkdir(parents=True, exist_ok=True)
    ANNOTATIONS.write_text(json.dumps(current, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"added {a.guid} ({len(entry['segments'])} segments); {len(current)} annotated cues")


if __name__ == "__main__":
    main()
