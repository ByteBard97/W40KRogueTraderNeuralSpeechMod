"""Per-line voice routes for unnamed lines, written by the Voice Studio into data/studio/pools.json."""
from __future__ import annotations

import json
from pathlib import Path

POOLS = Path(__file__).resolve().parents[2] / "data/studio/pools.json"
SLOT_PREFIX = "pool_"


def load_routes(path: Path = POOLS) -> dict[str, dict]:
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for guid, r in (json.loads(path.read_text(encoding="utf-8")).get("routes") or {}).items():
        if r["to"] == "narrator":
            out[guid] = {"narrator": True, "speaker": None}
        elif r["to"] == "speaker" and r.get("speaker"):
            out[guid] = {"narrator": False, "speaker": r["speaker"]}
        elif r["to"] == "slot" and r.get("slot"):
            out[guid] = {"narrator": False, "speaker": SLOT_PREFIX + r["slot"]}
    return out


def resolve(routes: dict, guid: str, kind: str | None, speaker: str | None, is_narrator: bool):
    """(speaker, is_narrator, routed_from). Only the unnamed default speaker is rerouted; narration stays narration."""
    hit = routes.get(guid) if kind == "default_speaker" else None
    if hit is None or is_narrator:
        return speaker, is_narrator, None
    if hit["narrator"]:
        return "narrator", True, kind
    return hit["speaker"], False, kind
