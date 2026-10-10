from __future__ import annotations

import re
import shutil
import time
from collections import Counter

from . import pools, speakers
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

LABELS = ("machine", "vox_channel", "helmet", "ethereal", "monstrous", "cavernous")
SAMPLE_LINES = 5
DEFAULT_DSP = "chain.dsp"
DEFAULT_VERSION = "v1"
BACKUP_NAME = re.compile(r"^(assignments|fx_labels)\.\d{4}-\d\d-\d\dT\d\d-\d\d-\d\d(-\d+)?\.bak\.json$")
_VERSION = re.compile(r"^(v\d+)\s+", re.I)


def labels_path(cfg: Config):
    return cfg.studio / "fx_labels.json"


def assignments_path(cfg: Config):
    return cfg.data / "fx_lab/assignments.json"


def family_version(name: str, given: dict | None = None) -> tuple[str, str]:
    """('Machine', 'v2') from 'v2 Machine: servitor'. A `family` or `version` key on the scenario/preset wins."""
    given = given or {}
    m = _VERSION.match(name)
    version = given.get("version") or (m.group(1).lower() if m else DEFAULT_VERSION)
    rest = name[m.end():] if m else name
    family = given.get("family") or (rest.split(":", 1)[0] if ":" in rest else re.split(r"\s*[+(]", rest, maxsplit=1)[0]).strip() or rest
    return family, version


def _entry(name: str, source: str, p: dict) -> dict:
    family, version = family_version(name, p)
    return {"name": name, "source": source, "dsp": p.get("dsp", DEFAULT_DSP), "notes": p.get("notes", ""),
            "family": family, "version": version}


def library(cfg: Config) -> list[dict]:
    """Scenario names plus saved presets. A saved preset wins over a scenario of the same name, as in batch.py."""
    out: dict[str, dict] = {}
    for s in read_json(cfg.root / "tools/fx_lab/scenarios.json", {"scenarios": []})["scenarios"]:
        out[s["name"]] = _entry(s["name"], "scenario", {**s, "notes": s.get("notes", "")})
    for name, p in read_json(cfg.data / "fx_lab/presets.json", {}).items():
        out[name] = _entry(name, "saved", p)
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
        if labels_path(cfg).exists() and read_json(labels_path(cfg), {}) != merged:
            _backup(labels_path(cfg), "fx_labels")
        write_json_atomic(labels_path(cfg), merged)
    return merged


def _backup(path, prefix: str) -> str:
    """Copy `path` to <prefix>.<timestamp>.bak.json beside it and return the new file name."""
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    dst, n = path.with_name(f"{prefix}.{stamp}.bak.json"), 1
    while dst.exists():
        n += 1
        dst = path.with_name(f"{prefix}.{stamp}-{n}.bak.json")
    shutil.copyfile(path, dst)
    return dst.name


def _line_info(cfg: Config) -> dict[str, dict]:
    """guid -> {labels, entry} for every unnamed line, first roster occurrence wins (as in expand)."""
    unnamed = {j["guid"] for j in pools._unnamed_jobs(cfg)}
    out: dict[str, dict] = {}
    for conv in pools._roster(cfg):
        for ln in conv["lines"]:
            guid = ln["key"]
            if guid in unnamed and guid not in out:
                out[guid] = {"labels": list(ln.get("fx") or []), "entry": f"{conv['conversation']}|{ln['speaker']}"}
    return out


def expand(cfg: Config) -> dict:
    """The assignments.json shape batch.py reads: {"speakers": {name: [presets]}, "lines": {guid: [presets]}}."""
    labels = get_labels(cfg)
    lines: dict[str, list[str]] = {}
    unmapped: Counter = Counter()
    for guid, info in _line_info(cfg).items():
        chain: list[str] = []
        for label in info["labels"]:
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


def _voices(cfg: Config) -> tuple[dict[str, str], dict[str, str]]:
    """guid -> voice key ('slot:male_human', 'speaker:Idira', 'narrator', or 'entry:<conv>|<id>' before pools exist) and
    voice key -> display name."""
    st = read_json(pools.pools_path(cfg), None)
    info = _line_info(cfg)
    key, name = {}, {}
    for guid, i in info.items():
        r = (st or {}).get("routes", {}).get(guid)
        if r is None:
            key[guid] = f"entry:{i['entry']}"
            name[key[guid]] = i["entry"]
        elif r["to"] == "slot":
            key[guid] = f"slot:{r.get('slot')}"
            name[key[guid]] = (st["slots"].get(r.get("slot")) or {}).get("name") or str(r.get("slot"))
        elif r["to"] == "speaker":
            key[guid] = f"speaker:{r.get('speaker')}"
            name[key[guid]] = r.get("speaker")
        else:
            key[guid] = "narrator"
            name[key[guid]] = "Narrator"
    return key, name


def usage(cfg: Config) -> dict:
    """Per label: lines carrying it and distinct voices (pool slots / named speakers / narrator) those lines go to."""
    voice, _ = _voices(cfg)
    lines: Counter = Counter()
    who: dict[str, set] = {l: set() for l in LABELS}
    for guid, info in _line_info(cfg).items():
        for label in set(info["labels"]):
            lines[label] += 1
            who.setdefault(label, set()).add(voice[guid])
    labels = get_labels(cfg)
    return {"labels": {l: {"lines": lines.get(l, 0), "speakers": len(who.get(l, ())), "presets": len(labels.get(l, []))}
                       for l in LABELS},
            "pools_built": pools.pools_path(cfg).exists()}


def _common(chains: list[list[str]]) -> list[str]:
    """The chain most lines of a voice carry (lines without any FX do not vote)."""
    voted = [tuple(c) for c in chains if c]
    return list(Counter(voted).most_common(1)[0][0]) if voted else []


def diff(cfg: Config) -> dict:
    """What Write would change: one row per voice (and one per active speaker profile), changed rows first."""
    e = expand(cfg)
    path = assignments_path(cfg)
    current = read_json(path, {"speakers": {}, "lines": {}})
    now_lines, now_people = current.get("lines", {}), current.get("speakers", {})
    voice, names = _voices(cfg)
    info = _line_info(cfg)
    exported = speakers._export_index(cfg)
    groups: dict[str, list[str]] = {}
    for guid in info:
        groups.setdefault(voice[guid], []).append(guid)
    rows = []
    for vk, guids in groups.items():
        labels = sorted({l for g in guids for l in info[g]["labels"]})
        before = [now_lines.get(g, []) for g in guids]
        after = [e["lines"].get(g, []) for g in guids]
        sample = next((f"data/render/export/{exported[g]['wav']}" for g in guids
                       if g in exported and (cfg.render / "export" / exported[g]["wav"]).is_file()), None)
        changed = sum(b != a for b, a in zip(before, after))
        if not labels and not any(before):
            continue
        rows.append({"voice": vk, "kind": vk.split(":", 1)[0] if ":" in vk else vk, "speaker": names[vk], "labels": labels,
                     "lines": len(guids), "now": _common(before), "after": _common(after), "changed": bool(changed),
                     "changed_lines": changed, "sample_wav": sample})
    for who in sorted(set(e["speakers"]) | set(now_people)):
        b, a = list(now_people.get(who, [])), list(e["speakers"].get(who, []))
        rows.append({"voice": f"profile:{who}", "kind": "profile", "speaker": who, "labels": [], "lines": 0, "now": b,
                     "after": a, "changed": a != b, "changed_lines": int(a != b), "sample_wav": None})
    rows.sort(key=lambda r: (not r["changed"], -r["lines"], r["speaker"]))
    return {"rows": rows, "changed": sum(r["changed"] for r in rows), "unmapped_labels": e["unmapped"],
            "file_mtime": path.stat().st_mtime_ns if path.exists() else None}


def preview(cfg: Config) -> dict:
    e = expand(cfg)
    return {"lines": len(e["lines"]), "speakers": len(e["speakers"]), "unmapped_labels": e["unmapped"],
            "sample": [{"guid": g, "presets": p} for g, p in list(e["lines"].items())[:SAMPLE_LINES]]}


def write(cfg: Config) -> dict:
    e = expand(cfg)
    path = assignments_path(cfg)
    affected = diff(cfg)["changed"]
    with STATE_LOCK:
        backup = _backup(path, "assignments") if path.exists() else None
        write_json_atomic(path, {"speakers": e["speakers"], "lines": e["lines"]})
    return {"path": "data/fx_lab/assignments.json", "lines": len(e["lines"]), "speakers": len(e["speakers"]),
            "backup": backup, "affected_speakers": affected}


def backups(cfg: Config) -> list[dict]:
    """Timestamped backups of assignments.json and fx_labels.json, newest first."""
    out = []
    for d, kind, rel in ((assignments_path(cfg).parent, "assignments", "data/fx_lab"), (cfg.studio, "labels", "data/studio")):
        for f in d.glob("*.bak.json") if d.is_dir() else ():
            if BACKUP_NAME.match(f.name) and f.name.startswith("assignments." if kind == "assignments" else "fx_labels."):
                out.append({"name": f.name, "kind": kind, "path": f"{rel}/{f.name}", "mtime": f.stat().st_mtime_ns,
                            "size": f.stat().st_size})
    return sorted(out, key=lambda b: (b["mtime"], b["name"]), reverse=True)


def restore(cfg: Config, name: str) -> dict:
    """Put a backup back as the live file. The file it replaces is itself backed up first, so a restore can be undone."""
    found = next((b for b in backups(cfg) if b["name"] == name), None) if isinstance(name, str) else None
    if found is None:
        raise ApiError(404, f"no backup {name!r}")
    live = assignments_path(cfg) if found["kind"] == "assignments" else labels_path(cfg)
    with STATE_LOCK:
        safety = _backup(live, live.name.removesuffix(".json")) if live.exists() else None
        shutil.copyfile(cfg.root / found["path"], live)
    return {"restored": name, "kind": found["kind"], "path": str(live.relative_to(cfg.root)), "backup": safety}
