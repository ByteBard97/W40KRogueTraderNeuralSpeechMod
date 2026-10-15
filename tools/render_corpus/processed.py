"""Speakers whose voice is processed (machine, vox, radio, ...) need more denoising steps when cloned: VoxCPM2 at 15 steps smears them.

A speaker is processed when (in order): the owner says so in data/studio/npc_processing.json ({speaker: true|false}, always wins), or the
BG3 voice they are cast as is labelled processed (casting.json), or the owner labelled the speaker's own game voice (rt_labels.json), or the automatic assignment picked a processed voice (auto_cast.json), or
they are a pool slot of machines. `apply` marks such jobs and raises their recipe to PROCESSED_TIMESTEPS; the queue calls it as it loads
jobs, so workers on any machine render at the higher count without needing updated code (the recipe travels with the job).
"""
from __future__ import annotations

import json
from pathlib import Path

PROCESSED_TIMESTEPS = 20
MACHINE_SPECIES = {"machine", "necron"}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def load(root: Path) -> set[str]:
    """Every speaker key whose clones should render with PROCESSED_TIMESTEPS."""
    d = root / "data/studio"
    labels = _read(d / "bg3_labels.json")
    processed_voice = {slug for slug, mine in labels.items() if "processed" in ([mine.get("processing")] if isinstance(mine.get("processing"), str) else mine.get("processing") or [])}
    out = {sp for sp, a in (_read(d / "casting.json").get("assignments") or {}).items() if a.get("bg3") in processed_voice}
    out |= {k for k, it in (_read(d / "auto_cast.json").get("items") or {}).items() if it.get("processed")}
    out |= {s.get("speaker_key") or f"pool_{sid}" for sid, s in (_read(d / "pools.json").get("slots") or {}).items() if s.get("species") in MACHINE_SPECIES}
    for speaker, mine in _read(d / "rt_labels.json").items():             # the owner's labels on voiced speakers (Voice Studio, RT Voices)
        kind = mine.get("processing")
        kind = [kind] if isinstance(kind, str) else kind or []
        if "processed" in kind:
            out.add(speaker)
        elif kind:
            out.discard(speaker)
    for speaker, yes in _read(d / "npc_processing.json").items():
        (out.add if yes else out.discard)(speaker)
    return out


def apply(jobs: list[dict], speakers: set[str]) -> list[dict]:
    """Mark the jobs of processed speakers, and raise (never lower) their recipe's steps. The recipe dict is copied, not changed in place."""
    out = []
    for j in jobs:
        if j.get("speaker") not in speakers:
            out.append(j)
            continue
        j = {**j, "processed": True}
        r = j.get("recipe")
        if r:
            steps = max(int(r.get("timesteps", 0)), PROCESSED_TIMESTEPS)
            name = r.get("name", "recipe")
            j["recipe"] = {**r, "timesteps": steps, "name": name if name.endswith(f"+p{steps}") else f"{name}+p{steps}"}
        out.append(j)
    return out
