from __future__ import annotations

import json
import re
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

_CACHE: dict[Path, tuple[int, object]] = {}


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "unnamed"


def studio_dir(cfg: Config, slug: str) -> Path:
    return cfg.studio / slug


def _cached(path: Path, load):
    """Parse big files once per modification time (jobs.jsonl is ~26k rows)."""
    if not path.exists():
        return load(None)
    mtime = path.stat().st_mtime_ns
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    val = load(path)
    _CACHE[path] = (mtime, val)
    return val


def _jobs(cfg: Config) -> list[dict]:
    def load(p):
        if p is None:
            return []
        return [json.loads(ln) for ln in p.open(encoding="utf-8") if ln.strip()]
    return _cached(cfg.render / "jobs.jsonl", load)


def _export_index(cfg: Config) -> dict:
    return _cached(cfg.render / "export/index.json", lambda p: {} if p is None else json.loads(p.read_text(encoding="utf-8")))


def _designed(cfg: Config) -> dict:
    return read_json(cfg.voice_design / "design_manifest.json", {})


def _real_names(cfg: Config) -> list[str]:
    return list(read_json(cfg.voices / "prompts/prompts.json", {}))


def _assign_slugs(cfg: Config, names: list[str]) -> dict[str, str]:
    """Slugs are remembered in data/studio/_slugs.json and never reassigned, so a profile saved under a slug stays with
    the same speaker even when a later name slugifies the same (the new name gets the suffix, whatever the sort order)."""
    path = cfg.studio / "_slugs.json"
    with STATE_LOCK:
        reg = read_json(path, {})
        used, changed = set(reg.values()), False
        for name in sorted(names, key=str.lower):
            if name in reg:
                continue
            base = slug = slugify(name)
            i = 2
            while slug in used:
                slug, i = f"{base}_{i}", i + 1
            reg[name] = slug
            used.add(slug)
            changed = True
        if changed:
            write_json_atomic(path, reg)
    return reg


def list_speakers(cfg: Config) -> list[dict]:
    audit = read_json(cfg.voice_design / "audit.json", {})
    counts: dict[str, int] = {}
    for j in _jobs(cfg):
        counts[j["speaker"]] = counts.get(j["speaker"], 0) + 1
    designed = _designed(cfg)      # a name in the design manifest stays "designed" even after its pick is registered
    entries = [(n, "designed") for n in designed] + [(n, "real") for n in _real_names(cfg) if n not in designed]
    slugs = _assign_slugs(cfg, [n for n, _ in entries])
    out = []
    for name, origin in sorted(entries, key=lambda e: e[0].lower()):
        slug = slugs[name]
        if (studio_dir(cfg, slug) / "profile.json").exists():
            status = "profile"
        elif origin == "real" or (audit.get(name) or {}).get("pick"):
            status = "source"
        else:
            status = "needs_voice"
        out.append({"slug": slug, "name": name, "origin": origin, "line_count": counts.get(name, 0), "status": status})
    return out


def find_speaker(cfg: Config, slug: str) -> dict:
    for s in list_speakers(cfg):
        if s["slug"] == slug:
            return s
    raise ApiError(404, f"no speaker '{slug}'")


def _clips(cfg: Config, name: str) -> list[dict]:
    prompts = read_json(cfg.voices / "prompts/prompts.json", {}).get(name, [])
    curated = {p["event"]: p for p in prompts}
    out, seen = [], set()
    for e in read_json(cfg.voices / "catalog.json", {}).values():
        if e["speaker"] != name:
            continue
        seen.add(e["event"])
        pr = curated.get(e["event"])
        out.append({"id": e["event"], "wav": "data/voices/" + e["wav"], "duration": e["duration"],
                    "text": " ".join(t["text"] for t in e["texts"]),
                    "curated_rank": pr["rank"] if pr else None, "noise_db": pr.get("noise_db") if pr else None})
    for p in prompts:   # prompt-bank clips with no catalog entry: registered designed voices, narrator clips
        if p["event"] not in seen:
            out.append({"id": p["event"], "wav": "data/voices/" + p["wav"], "duration": p.get("duration", 0.0),
                        "text": p.get("text", ""), "curated_rank": p.get("rank"), "noise_db": p.get("noise_db")})
    out.sort(key=lambda c: (c["curated_rank"] is None, c["curated_rank"] or 0, c["id"]))
    return out


def _design(cfg: Config, name: str) -> dict | None:
    m = _designed(cfg).get(name)
    if not m:
        return None
    a = read_json(cfg.voice_design / "audit.json", {}).get(name) or {}
    scores = read_json(cfg.voice_design / "scores.json", {})
    gen = m.get("gen", {}).get("candidates", {})
    cands = [{"id": c, "file": f"data/voice_design/clips/{m['slug']}/{c}",
              "scores": scores.get(f"clips/{m['slug']}/{c}"), "verdict": (a.get("cands") or {}).get(c, {}),
              "gen": gen.get(c)} for c in m["candidates"]]
    order = [c for c in a.get("order", []) if c in m["candidates"]]
    cands.sort(key=lambda c: (c["id"] not in order, order.index(c["id"]) if c["id"] in order else 0))
    desc = read_json(cfg.voice_design / "overrides.json", {}).get(name, m["description"])
    return {"description": desc, "text": m["text"], "candidates": cands, "order": order, "pick": a.get("pick")}


def speaker_detail(cfg: Config, slug: str) -> dict:
    s = find_speaker(cfg, slug)
    return {"summary": s, "clips": _clips(cfg, s["name"]),
            "design": _design(cfg, s["name"]) if s["origin"] == "designed" else None,
            "profile": read_json(studio_dir(cfg, slug) / "profile.json", None)}


def speaker_lines(cfg: Config, name: str) -> list[dict]:
    index = _export_index(cfg)
    out = []
    for j in _jobs(cfg):
        if j["speaker"] != name:
            continue
        a = j.get("annotation") or {}
        wav = index.get(j["guid"], {}).get("wav")
        out.append({"guid": j["guid"], "text": j["text"], "emotion": a.get("emotion"), "intensity": a.get("intensity"),
                    "pace": a.get("pace"), "instruct": a.get("instruct"),
                    "baseline": f"data/render/export/{wav}" if wav else None})
    return out
