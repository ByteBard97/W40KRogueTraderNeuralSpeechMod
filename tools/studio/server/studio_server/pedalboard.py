"""Server side of the pedalboard: serves the Faust block library, and stores graphs with their generated program and preset entry.

The browser builds the graph and generates the Faust code (TypeScript); this module only validates and persists. A save writes three
things, in an order chosen so a failure part-way never corrupts the shared presets.json: the program (.dsp), the graph, and last the
preset entry, so an interrupted save at worst leaves an unreferenced file.
"""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

NAME_RX = re.compile(r"[A-Za-z0-9_-]{1,60}")
GRAPH_VERSION = 1
FAUST_DIR = ("tools", "fx_lab", "faust")
PRESET_DIR = "presets"
BACKUP_MIN_INTERVAL_S = 600          # one presets.json backup per ten minutes, however many saves happen in between
BACKUP_PREFIX, BACKUP_SUFFIX = "presets.", ".bak.json"
BACKUP_STAMP = "%Y%m%d-%H%M%S"


def _faust(cfg: Config) -> Path:
    return cfg.root.joinpath(*FAUST_DIR)


def _graphs_dir(cfg: Config) -> Path:
    return cfg.data / "fx_lab" / "graphs"


def _presets_path(cfg: Config) -> Path:
    return cfg.data / "fx_lab" / "presets.json"


def check_name(name) -> str:
    """Reject anything that is not a plain short name before it can reach a path (traversal, dots, slashes, empty, long)."""
    if not isinstance(name, str) or not NAME_RX.fullmatch(name):
        raise ApiError(400, "graph name must be 1 to 60 characters of letters, digits, underscore or hyphen")
    return name


def blocks(cfg: Config) -> dict:
    lib, catalog = _faust(cfg) / "blocks.lib", _faust(cfg) / "catalog.json"
    for p in (lib, catalog):
        if not p.is_file():
            raise ApiError(404, f"{p.name} not found in tools/fx_lab/faust (the block library has not been built yet)")
    return {"lib": lib.read_text(encoding="utf-8"), "catalog": read_json(catalog, None)}


def list_graphs(cfg: Config) -> list[dict]:
    """Saved graphs, newest first. `updated` is the file's modification time as ISO text."""
    found = sorted(_graphs_dir(cfg).glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    return [{"name": p.stem, "updated": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")} for p in found]


def load_graph(cfg: Config, name: str) -> dict:
    path = _graphs_dir(cfg) / f"{check_name(name)}.json"
    if not path.is_file():
        raise ApiError(404, f"no saved graph named {name}")
    return read_json(path, None)


def _validate(body: dict) -> tuple[dict, str, dict, str]:
    graph, code, params = body.get("graph"), body.get("code"), body.get("params")
    notes = body.get("notes") or ""
    if not isinstance(graph, dict):
        raise ApiError(400, "graph must be an object")
    check_name(graph.get("name"))
    if graph.get("version") != GRAPH_VERSION or isinstance(graph.get("version"), bool):
        raise ApiError(400, f"graph.version must be {GRAPH_VERSION}")
    if not isinstance(graph.get("nodes"), list) or not isinstance(graph.get("edges"), list):
        raise ApiError(400, "graph.nodes and graph.edges must be lists")
    if not isinstance(code, str) or "process" not in code:
        raise ApiError(400, "code must be a Faust program containing process")
    if not isinstance(params, dict) or not all(
            isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool) for k, v in params.items()):
        raise ApiError(400, "params must be a flat object of parameter key to number")
    if not isinstance(notes, str):
        raise ApiError(400, "notes must be a string")
    return graph, code, params, notes


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _backup_presets(path: Path) -> None:
    """Copy a non-empty presets.json aside, at most once per BACKUP_MIN_INTERVAL_S. Old backups are never removed."""
    if not path.is_file() or path.stat().st_size == 0:
        return
    newest = max((p.stat().st_mtime for p in path.parent.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")), default=0.0)
    if time.time() - newest < BACKUP_MIN_INTERVAL_S:
        return
    stamp = datetime.now().strftime(BACKUP_STAMP)
    shutil.copy2(path, path.with_name(f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"))


def save_graph(cfg: Config, body: dict) -> dict:
    graph, code, params, notes = _validate(body)
    name = graph["name"]
    dsp_rel = f"{PRESET_DIR}/{name}.dsp"
    with STATE_LOCK:
        presets_path = _presets_path(cfg)
        presets = read_json(presets_path, {})
        _backup_presets(presets_path)
        write_text_atomic(_faust(cfg) / dsp_rel, code)
        write_json_atomic(_graphs_dir(cfg) / f"{name}.json", graph)
        presets[name] = {"dsp": dsp_rel, "params": params, "graph": graph, "notes": notes}
        write_json_atomic(presets_path, presets)
    return {"name": name, "dsp": dsp_rel, "saved": True}
