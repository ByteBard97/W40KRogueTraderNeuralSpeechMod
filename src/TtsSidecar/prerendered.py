"""Serve pre-rendered best-of-N winners (from tools/scorer/loop.py) ahead of live synthesis.

Each character's export lives in data/bon/<speaker>/export/{index.json,wav/<guid>.wav}. A request is
served from there only when its cue_guid has a winner AND the request text still matches the text the
winner was rendered from, so an edited line falls through to live synthesis instead of playing stale audio.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def load_index(bon_root: Path, render_root: Path | None = None) -> dict[str, dict]:
    """guid -> {"wav": absolute path, "text": str, "speaker": str, ...} across all exports.

    bon_root/<speaker>/export holds reviewed best-of-N winners. render_root/export (tools/render_corpus)
    holds the bulk render, and render_root/export_fx the same lines after per-speaker voice FX
    (tools/voice_design/apply_fx.py), which override the raw ones. Reviewed winners override both. Render
    entries match on guid alone ("match": "guid") because they were rendered from cleaned text.
    """
    index: dict[str, dict] = {}
    idxs = sorted(bon_root.glob("*/export/index.json"))
    if render_root is not None:  # lowest priority first: raw render, then FX-processed, then reviewed winners
        idxs = [render_root / "export" / "index.json", render_root / "export_fx" / "index.json"] + idxs
    for idx in idxs:
        speaker_dir = idx.parent
        try:
            entries = json.loads(idx.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for guid, e in entries.items():
            wav = speaker_dir / e["wav"]
            if wav.is_file():
                index[guid] = {"speaker": speaker_dir.parent.name, **e, "wav": wav}
    return index


def lookup(index: dict[str, dict], cue_guid: str | None, text: str) -> Path | None:
    e = index.get(cue_guid) if cue_guid else None
    if e is None or (e.get("match") != "guid" and _norm(e["text"]) != _norm(text)):
        return None
    return e["wav"]
