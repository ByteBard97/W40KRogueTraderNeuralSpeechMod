from __future__ import annotations

import shutil
from collections import Counter

from . import pools, speakers
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

LABELS = ("machine", "vox_channel", "helmet", "ethereal", "monstrous", "cavernous")
SAMPLE_LINES = 5
DEFAULT_DSP = "chain.dsp"


def labels_path(cfg: Config):
    return cfg.studio / "fx_labels.json"


def assignments_path(cfg: Config):
    return cfg.data / "fx_lab/assignments.json"


def library(cfg: Config) -> list[dict]:
    """Scenario names plus saved presets. A saved preset wins over a scenario of the same name, as in batch.py."""
    out: dict[str, dict] = {}
    for s in read_json(cfg.root / "tools/fx_lab/scenarios.json", {"scenarios": []})["scenarios"]:
        out[s["name"]] = {"name": s["name"], "source": "scenario", "dsp": s.get("dsp", DEFAULT_DSP), "notes": s.get("notes", "")}
    for name, p in read_json(cfg.data / "fx_lab/presets.json", {}).items():
        out[name] = {"name": name, "source": "saved", "dsp": p.get("dsp", DEFAULT_DSP), "notes": p.get("notes", "")}
    return sorted(out.values(), key=lambda p: p["name"])


def get_labels(cfg: Config) -> dict[str, list[str]]:
    saved = read_json(labels_path(cfg), {})
    return {label: list(saved.get(label, [])) for label in LABELS}


def save_labels(cfg: Config, body: dict) -> dict[str, list[str]]:
    names = {p["name"] for p in library(cfg)}
    for label, presets in body.items():
        if label not in LABELS:
            raise ApiError(400, f"unknown label {label!r}")
        if not isinstance(presets, list) or any(p not in names for p in presets):
            raise ApiError(400, f"{label}: every preset must be in the library")
    with STATE_LOCK:
        merged = {**get_labels(cfg), **{k: list(v) for k, v in body.items()}}
        write_json_atomic(labels_path(cfg), merged)
    return merged


def expand(cfg: Config) -> dict:
    """The assignments.json shape batch.py reads: {"speakers": {name: [presets]}, "lines": {guid: [presets]}}."""
    labels = get_labels(cfg)
    unnamed = {j["guid"] for j in pools._unnamed_jobs(cfg)}
    lines: dict[str, list[str]] = {}
    seen: set[str] = set()
    unmapped: Counter = Counter()
    for conv in pools._roster(cfg):
        for ln in conv["lines"]:
            guid = ln["key"]
            if guid not in unnamed or guid in seen:
                continue
            seen.add(guid)
            chain: list[str] = []
            for label in ln.get("fx") or []:
                if not labels.get(label):
                    unmapped[label] += 1
                for preset in labels.get(label, []):
                    if preset not in chain:
                        chain.append(preset)
            if chain:
                lines[guid] = chain
    people: dict[str, list[str]] = {}
    for s in speakers.list_speakers(cfg):
        active = read_json(speakers.studio_dir(cfg, s["slug"]) / "active.json", None)
        if active and active.get("fx"):
            people[active["name"]] = list(active["fx"])
    return {"speakers": people, "lines": lines, "unmapped": dict(unmapped)}


def preview(cfg: Config) -> dict:
    e = expand(cfg)
    return {"lines": len(e["lines"]), "speakers": len(e["speakers"]), "unmapped_labels": e["unmapped"],
            "sample": [{"guid": g, "presets": p} for g, p in list(e["lines"].items())[:SAMPLE_LINES]]}


def write(cfg: Config) -> dict:
    e = expand(cfg)
    path = assignments_path(cfg)
    with STATE_LOCK:
        if path.exists():
            shutil.copyfile(path, path.with_name(path.name + ".bak"))
        write_json_atomic(path, {"speakers": e["speakers"], "lines": e["lines"]})
    return {"path": "data/fx_lab/assignments.json", "lines": len(e["lines"]), "speakers": len(e["speakers"])}
