"""Automatic casting: a BG3 voice for every Rogue Trader character that has none, chosen from the owner's BG3 labels.

Targets are the characters not cast yet (data/npc_profile/describe/casting_needs.json minus data/studio/casting.json) and the unnamed speaker
groups the Pools page routes to a pool slot (one target per group, so each gets its own voice). The rules are in auto_cast_rules; this module
loads the data, saves the result in data/studio/auto_cast.json, and keeps the owner's overrides across re-runs. Hand-made casting is never touched.
A target with too little known about it (see auto_cast_rules.missing_info) is not assigned; it is listed as needing research.
"""
from __future__ import annotations

import json
import time
from collections import Counter

from . import auto_cast_rules as R
from . import bg3_labels, casting, speakers
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

ROSTER = "data/npc_profile/roster_35b_all.json"
GROUP_PREFIX = "group:"
SAMPLE_LINES = 3
MIN_VOICE_LINES = 30                 # fewer lines than this and the reference clip is too thin to clone from


def path(cfg: Config):
    return cfg.studio / "auto_cast.json"


def read(cfg: Config) -> dict:
    s = read_json(path(cfg), {}) or {}
    s.setdefault("items", {})
    return s


def _norm(entry: str) -> str:
    conv, _, ident = (entry or "").partition("|")
    return f"{conv.strip()}|{ident.strip()}"


def _roster(cfg: Config) -> dict[str, dict]:
    rows = json.loads((cfg.root / ROSTER).read_text(encoding="utf-8")) if (cfg.root / ROSTER).is_file() else []
    return {_norm(f"{c.get('conversation')}|{r.get('id')}"): r for c in rows for r in c.get("roster", [])}


def group_targets(cfg: Config) -> list[dict]:
    """One target per unnamed group the Pools page routes to a pool slot."""
    pools = read_json(cfg.studio / "pools.json", {}) or {}
    roster = _roster(cfg)
    groups: dict[str, dict] = {}
    for guid, r in (pools.get("routes") or {}).items():
        if r.get("to") != "slot" or not r.get("entry"):
            continue
        key = _norm(r["entry"])
        g = groups.setdefault(key, {"guids": [], "attr": r.get("attr") or {}, "slot": r.get("slot")})
        g["guids"].append(guid)
    out = []
    for key, g in groups.items():
        ro = roster.get(key) or {}
        attr = g["attr"]
        pick = lambda f: next((x for x in (ro.get(f), attr.get(f)) if x not in (None, "", "unknown")), None)
        out.append({"key": GROUP_PREFIX + key, "kind": "group", "name": ro.get("name") or ro.get("label") or key.split("|")[-1],
                    "guessed_name": ro.get("name"), "gender": pick("gender"), "species": pick("species"), "age": pick("age"),
                    "role": ro.get("role") or "", "description": ro.get("baseline_voice") or "", "evidence": ro.get("evidence") or [],
                    "fx": ro.get("fx") or [], "lines": len(g["guids"]), "conversation": key.split("|")[0], "guids": g["guids"], "slot": g["slot"]})
    return out


def character_targets(cfg: Config) -> list[dict]:
    cast = casting.state(cfg)["assignments"]
    return [{"key": r["speaker"], "kind": "character", "name": r["speaker"], "gender": r.get("gender"), "species": r.get("species"),
             "age": r.get("age"), "role": r.get("role") or "", "description": r.get("voice_description") or "", "evidence": [], "fx": [],
             "lines": r["lines"], "conversation": None, "guids": [], "slot": r.get("pool_slot")}
            for r in casting.targets(cfg) if r["kind"] == "character" and r["speaker"] not in cast]


def usable_voices(cfg: Config) -> list[dict]:
    """The BG3 voices the owner has not ruled out, with a clip long enough to clone from."""
    out = []
    for v in casting.bg3_voices(cfg):
        if v["mine"].get("reserve") == bg3_labels.DO_NOT_USE or v["lines"] < MIN_VOICE_LINES or not v["refs"]:
            continue
        if v["name"].lower() in casting.NOT_CASTABLE or "player voice" in v["name"].lower():
            continue
        out.append({"slug": v["slug"], "name": v["name"], "lines": v["lines"], "refs_quality": v["quality"], "labels": v["labels"],
                    "non_human": v["non_human"], "gender": v["gender"]})
    return out


def _meta(t: dict) -> dict:
    return {k: t[k] for k in ("kind", "name", "guessed_name", "gender", "species", "age", "role", "description", "lines", "conversation", "slot", "learned") if k in t}


def apply_research(cfg: Config, targets: list[dict]) -> None:
    """Fill a missing gender or species from what the game text made plain (auto_cast_research); known values are never overwritten."""
    found = read_json(cfg.studio / "auto_cast_research.json", {}) or {}
    for t in targets:
        facts = (found.get(t["key"]) or {}).get("facts") or {}
        for field, blank in (("gender", (None, "", "unknown")), ("species", (None, "", "unknown"))):
            if t.get(field) in blank and facts.get(field):
                t[field] = facts[field]
                t.setdefault("learned", {})[field] = facts[field]


def run(cfg: Config) -> dict:
    """Work out every assignment again. Owner overrides stay; everything else is recomputed."""
    voices = usable_voices(cfg)
    by_slug = {v["slug"] for v in voices}
    with STATE_LOCK:
        old = read(cfg)["items"]
        kept = {k: v for k, v in old.items() if v.get("owner") and v.get("bg3") in by_slug}
        targets = character_targets(cfg) + group_targets(cfg)
        apply_research(cfg, targets)
        uses = Counter(a["bg3"] for a in casting.state(cfg)["assignments"].values()) + Counter(v["bg3"] for v in kept.values())
        ready, items = [], {}
        for t in targets:
            if t["key"] in kept:
                items[t["key"]] = {**kept[t["key"]], **_meta(t)}
                continue
            miss = R.missing_info(t)
            if miss:
                items[t["key"]] = {**_meta(t), "status": "needs_info", "missing": miss}
            else:
                ready.append(t)
        for key, a in R.assign(ready, voices, dict(uses)).items():
            t = next(x for x in ready if x["key"] == key)
            items[key] = {**_meta(t), "status": "assigned", **a}
        for t in ready:
            items.setdefault(t["key"], {**_meta(t), "status": "no_voice"})
        write_json_atomic(path(cfg), {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "items": items})
    return summary(items)


def summary(items: dict) -> dict:
    return {"total": len(items), **Counter(v["status"] for v in items.values())}


def override(cfg: Config, key: str, bg3: str | None) -> dict:
    """The owner picks a voice for one target (or, with None, hands it back to the rules on the next run)."""
    with STATE_LOCK:
        st = read(cfg)
        item = st["items"].get(key)
        if item is None:
            raise ApiError(404, f"unknown target {key!r}")
        if bg3 is None:
            item.pop("owner", None)
            item.update(status="needs_info" if item.get("missing") else "assigned")
        else:
            if not any(v["slug"] == bg3 for v in usable_voices(cfg)):
                raise ApiError(404, f"unknown or unusable BG3 voice {bg3!r}")
            voice = next(v for v in usable_voices(cfg) if v["slug"] == bg3)
            proc = "processed" in R._vals(voice, "processing")
            item.update(bg3=bg3, owner=True, status="assigned", processed=proc, steps=R.PROCESSED_STEPS if proc else R.DEFAULT_STEPS,
                        reasons=["picked by you"], alts=[], score=None)
        write_json_atomic(path(cfg), st)
    return item


def _group_texts(cfg: Config) -> dict[str, str]:
    return {j["guid"]: j["text"] for j in speakers._jobs(cfg) if j.get("text")}


def page(cfg: Config) -> dict:
    """Every target with its voice, a few lines it speaks, and the voice's name, for the browse page."""
    st = read(cfg)
    texts = _group_texts(cfg)
    voices = {v["slug"]: v for v in usable_voices(cfg)}
    samples = casting._samples(cfg)
    research = read_json(cfg.studio / "auto_cast_research.json", {}) or {}
    guids = {GROUP_PREFIX + k: g for k, g in ((t["key"][len(GROUP_PREFIX):], t["guids"]) for t in group_targets(cfg))}
    rows = []
    for key, it in st["items"].items():
        lines = [texts[g] for g in guids.get(key, []) if g in texts] if key.startswith(GROUP_PREFIX) else samples.get(key, [])
        lines = sorted(lines, key=lambda s: -len(s))[:SAMPLE_LINES]
        v = voices.get(it.get("bg3"))
        rows.append({"key": key, **it, "voice_name": v["name"] if v else None, "samples": lines, "research": (research.get(key) or {}).get("dossier"),
                     "alts": [{**a, "name": voices[a["bg3"]]["name"]} for a in it.get("alts", []) if a["bg3"] in voices]})
    rows.sort(key=lambda r: -r["lines"])
    return {"generated_at": st.get("generated_at"), "summary": summary(st["items"]), "items": rows}
