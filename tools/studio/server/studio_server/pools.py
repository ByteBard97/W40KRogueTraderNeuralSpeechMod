from __future__ import annotations

import json
import random
import re
import time
from collections import Counter

from . import speakers
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .pools_routing import DEFAULT_THRESHOLD, build_known, route_lines
from .pools_slots import MIN_SLOT_LINES, SLOT_PREFIX, assign_slots

ROSTER = "data/npc_profile/roster_35b_all.json"
CONVERSATIONS = "data/conversations.enGB.json"
DECISIONS = "data/npc_profile/match_decisions.json"
SPOT_CHECK_LINES = 10
MAX_PAGE = 500
QUEUE_SAMPLES = 3
SAMPLE_TEXT = ("The augurs report nothing unusual, my lord. We should hold our position "
               "until the situation becomes clear.")
AGE_WORDS = {"old": ", in their sixties", "young": ", in their twenties"}


def pools_path(cfg: Config):
    return cfg.studio / "pools.json"


def _state(cfg: Config) -> dict:
    st = read_json(pools_path(cfg), None)
    if st is None:
        raise ApiError(404, "pools are not built yet: POST /api/pools/rebuild")
    return st


def _unnamed_jobs(cfg: Config) -> list[dict]:
    """Lines spoken by the unnamed default speaker, including ones plan.py has since rerouted (routed_from)."""
    return [j for j in speakers._jobs(cfg)
            if j.get("routed_from") == "default_speaker" or (j["speaker"] == "default_speaker" and j.get("priority") == 3)]


def _roster(cfg: Config) -> list[dict]:
    path = cfg.root / ROSTER
    if not path.is_file():
        raise ApiError(404, f"harness roster not found: {ROSTER}")
    return speakers._cached(path, lambda p: json.loads(p.read_text(encoding="utf-8")))


def _banks(cfg: Config) -> set[str]:
    return set(read_json(cfg.voices / "prompts/prompts.json", {}))


def _known(cfg: Config) -> dict:
    path = cfg.root / CONVERSATIONS
    base = speakers._cached(path, lambda p: {} if p is None else build_known(json.loads(p.read_text(encoding="utf-8")), set()))
    banks = _banks(cfg)
    return {name: {**k, "has_bank": name in banks} for name, k in base.items()}


def _count_lines(routes: dict, slots: dict) -> None:
    n = Counter(r["slot"] for r in routes.values() if r["to"] == "slot")
    for sid, s in slots.items():
        s["lines"] = n.get(sid, 0)


def _describe(s: dict) -> str:
    who = {"male": "man", "female": "woman"}.get(s["gender"], "person")
    species = "" if s["species"] in ("human", "mixed") else f" ({s['species']})"
    return f"A {who}{species}{AGE_WORDS.get(s.get('age'), '')}, British English accent, clear and neutral speaking voice."


def ensure_slot_speakers(cfg: Config, slots: dict) -> int:
    """Add a design_manifest entry per slot so it appears as a designed speaker. Existing entries are never touched."""
    path = cfg.voice_design / "design_manifest.json"
    with STATE_LOCK:
        manifest = read_json(path, {})
        added = 0
        for s in slots.values():
            name = s["speaker_key"]
            if name in manifest:
                continue
            manifest[name] = {"slug": name, "gender": "Female" if s["gender"] == "female" else "Male", "role": "pool slot",
                              "description": s.get("description") or _describe(s), "text": SAMPLE_TEXT, "engine": "vox", "candidates": []}
            added += 1
        if added:
            write_json_atomic(path, manifest)
    return added


def rebuild(cfg: Config, threshold: float | None = None, min_slot_lines: int | None = None) -> dict:
    with STATE_LOCK:
        prev = read_json(pools_path(cfg), {})
        threshold = threshold if threshold is not None else prev.get("threshold", DEFAULT_THRESHOLD)
        min_lines = min_slot_lines if min_slot_lines is not None else prev.get("min_slot_lines", MIN_SLOT_LINES)
        guids = {j["guid"] for j in _unnamed_jobs(cfg)}
        decisions = read_json(cfg.root / DECISIONS, {})
        routes = route_lines(guids, _roster(cfg), _known(cfg), decisions, threshold)
        slots = assign_slots(routes, min_lines)
        prev_slots = prev.get("slots") or {}
        custom = dict(prev.get("custom_slots") or {})
        for sid, rec in custom.items():                            # hand-made slots exist whether or not any line routes to them
            slots.setdefault(sid, dict(rec))
        for sid, s in slots.items():
            if prev_slots.get(sid, {}).get("renamed"):
                s["name"], s["renamed"] = prev_slots[sid]["name"], True
        for guid, old in (prev.get("routes") or {}).items():       # user decisions and spot-check marks survive a rebuild
            new = routes.get(guid)
            if (new and old.get("checked") and new["source"] == "auto"
                    and old["to"] == new["to"] and old.get("slot") == new.get("slot")):
                routes[guid]["checked"] = True
                if "spot-check failed" in old.get("reasons", []):
                    routes[guid]["reasons"] = sorted(set(routes[guid]["reasons"]) | {"spot-check failed"})
            if old.get("source") == "override" and guid in routes:
                routes[guid] = old
                if old["to"] == "slot" and old["slot"] not in slots and old["slot"] in prev_slots:
                    slots[old["slot"]] = prev_slots[old["slot"]]
        merged = dict(prev.get("merged") or {})
        for src, dst in merged.items():                            # a user merge is an override: apply it after slot assignment
            if dst not in slots and dst in prev_slots:
                slots[dst] = prev_slots[dst]
            if dst not in slots:
                continue
            for r in routes.values():
                if r["to"] == "slot" and r.get("slot") == src:
                    r["slot"] = dst                       # a rename only: source and reasons stay
            slots.pop(src, None)
        _count_lines(routes, slots)
        write_json_atomic(pools_path(cfg), {
            "threshold": threshold, "min_slot_lines": min_lines, "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "slots": slots, "routes": routes, "spot": prev.get("spot", {}), "merged": merged,
            "custom_slots": custom, "merge_undo": prev.get("merge_undo", {})})
        ensure_slot_speakers(cfg, slots)
    return summary(cfg)


def _queued(st: dict) -> dict[str, dict]:
    return {g: r for g, r in st["routes"].items() if r["reasons"] and r["source"] == "auto"}


def _group(guid: str, r: dict) -> str:
    return r["entry"] or f"line:{guid}"


def summary(cfg: Config) -> dict:
    st = _state(cfg)
    dest = Counter()
    for r in st["routes"].values():
        dest["speaker_bank" if r["to"] == "speaker" and r.get("has_bank") else
             "speaker_nobank" if r["to"] == "speaker" else r["to"]] += 1
    by_name = {s["name"]: s["slug"] for s in speakers.list_speakers(cfg)}
    slots = [{**s, "slug": by_name.get(s["speaker_key"], s["speaker_key"]),
              "spot": st.get("spot", {}).get(sid, {"checked": 0, "wrong": 0})} for sid, s in st["slots"].items()]
    q = _queued(st)
    return {"threshold": st["threshold"], "built": st["built"], "total": len(st["routes"]),
            "destinations": {k: dest.get(k, 0) for k in ("narrator", "speaker_bank", "speaker_nobank", "slot")},
            "slots": sorted(slots, key=lambda s: -s["lines"]),
            "overrides": sum(1 for r in st["routes"].values() if r["source"] == "override"),
            "queue_lines": len(q), "queue_entries": len({_group(g, r) for g, r in q.items()})}


def _wav(cfg: Config, guid: str) -> str | None:
    """Repo-relative path of the rendered line (servable via /file), None when the line has no render."""
    wav = speakers._export_index(cfg).get(guid, {}).get("wav")
    return f"data/render/export/{wav}" if wav else None


def _entry_index(cfg: Config) -> dict[str, tuple[str, dict]]:
    index = {}
    for conv in _roster(cfg):
        for x in conv["roster"]:
            index[f"{conv['conversation']}|{x['id']}"] = (conv["conversation"], x)
    return index


def _row_matches(r: dict, text: str, x: dict, q: str | None, entry_name: str | None) -> bool:
    if entry_name and entry_name.lower() not in f"{x.get('name') or ''}\n{x.get('label') or ''}".lower():
        return False
    if q:
        hay = "\n".join([text, x.get("name") or "", x.get("label") or "", r.get("speaker") or ""]).lower()
        return q.lower() in hay
    return True


def routes_page(cfg: Config, *, to=None, slot=None, speaker=None, queued=None, offset=0, limit=100,
                q=None, conf_lt=None, bank=None, entry_name=None) -> dict:
    st = _state(cfg)
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    try:
        conf_lt = None if conf_lt in (None, "") else float(conf_lt)
    except ValueError:
        raise ApiError(400, f"conf_lt must be a number, got {conf_lt!r}")
    text = {j["guid"]: j["text"] for j in _unnamed_jobs(cfg)}
    index = _entry_index(cfg)
    rows = []
    for g, r in st["routes"].items():
        if to and r["to"] != to or slot and r.get("slot") != slot or speaker and r.get("speaker") != speaker:
            continue
        if queued is not None and bool(r["reasons"] and r["source"] == "auto") != bool(queued):
            continue
        if bank is not None and not (r["to"] == "speaker" and bool(r.get("has_bank")) == bool(bank)):
            continue
        if conf_lt is not None and (r.get("confidence") is None or r["confidence"] >= conf_lt):
            continue
        x = index.get(r["entry"] or "", (None, {}))[1]
        if not _row_matches(r, text.get(g, ""), x, q, entry_name):
            continue
        rows.append({"guid": g, "text": text.get(g, ""), **r, "entry_name": x.get("name"), "entry_label": x.get("label"),
                     "wav": _wav(cfg, g)})
    return {"total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}


def queue(cfg: Config) -> list[dict]:
    st = _state(cfg)
    text = {j["guid"]: j["text"] for j in _unnamed_jobs(cfg)}
    index = _entry_index(cfg)
    groups: dict[str, dict] = {}
    for g, r in _queued(st).items():
        key = _group(g, r)
        conv, x = index.get(r["entry"] or "", (None, {}))
        grp = groups.setdefault(key, {"key": key, "entry": r["entry"], "conversation": conv, "label": x.get("label") or "(no roster entry)",
                                      "name": x.get("name"), "role": x.get("role"), "attr": r.get("attr"), "reasons": [], "lines": 0,
                                      "samples": [], "sample_items": [],
                                      "to": r["to"], "slot": r.get("slot"), "speaker": r.get("speaker"),
                                      "evidence": (x.get("evidence") or [])[:QUEUE_SAMPLES]})
        grp["lines"] += 1
        grp["reasons"] = sorted(set(grp["reasons"]) | set(r["reasons"]))
        if len(grp["samples"]) < QUEUE_SAMPLES:
            grp["samples"].append(text.get(g, ""))
            grp["sample_items"].append({"guid": g, "text": text.get(g, ""), "wav": _wav(cfg, g)})
    return sorted(groups.values(), key=lambda g: -g["lines"])


def _targets(st: dict, body: dict) -> list[str]:
    if body.get("entry"):
        guids = [g for g, r in st["routes"].items() if r["entry"] == body["entry"]]
    else:
        guids = [g for g in body.get("guids", []) if g in st["routes"]]
    if not guids:
        raise ApiError(400, "no lines matched that entry or guid list")
    return guids


def override(cfg: Config, body: dict) -> dict:
    with STATE_LOCK:
        st = _state(cfg)
        guids = _targets(st, body)
        to_all = body.get("to")
        if to_all not in (None, "slot", "speaker", "narrator"):
            raise ApiError(400, f"unknown destination {to_all!r}")
        banks = _banks(cfg)
        updates, previous = {}, {}
        for g in guids:
            previous[g] = dict(st["routes"][g])
            r = dict(st["routes"][g])
            to = to_all or r["to"]
            if to == "slot":
                sid = body.get("slot", r.get("slot"))
                if sid not in st["slots"]:
                    raise ApiError(400, f"unknown slot {sid!r}")
                r.update(to="slot", slot=sid)
                r.pop("speaker", None), r.pop("has_bank", None)
            elif to == "speaker":
                name = (body.get("speaker") or r.get("speaker") or "").strip()
                if not name:
                    raise ApiError(400, "a speaker name is required")
                r.update(to="speaker", speaker=name, has_bank=name in banks)
                r.pop("slot", None)
            else:
                r.update(to="narrator")
                r.pop("slot", None), r.pop("speaker", None), r.pop("has_bank", None)
            r.update(source="override", reasons=[])
            updates[g] = r
        st["routes"].update(updates)
        _count_lines(st["routes"], st["slots"])
        write_json_atomic(pools_path(cfg), st)
    return {"changed": len(updates), "undo": {"previous": previous}}


def restore_routes(cfg: Config, previous) -> dict:
    """Write back the routes an override replaced (its `undo.previous`). All or nothing."""
    if not isinstance(previous, dict) or not previous:
        raise ApiError(400, "previous must be a non-empty {guid: route} object")
    with STATE_LOCK:
        st = _state(cfg)
        for g, r in previous.items():
            if g not in st["routes"]:
                raise ApiError(400, f"unknown line {g!r}")
            if not isinstance(r, dict) or r.get("to") not in ("slot", "speaker", "narrator"):
                raise ApiError(400, f"bad route for {g!r}")
            if r["to"] == "slot" and r.get("slot") not in st["slots"]:
                raise ApiError(400, f"slot {r.get('slot')!r} no longer exists (unmerge it first)")
        st["routes"].update({g: dict(r) for g, r in previous.items()})
        _count_lines(st["routes"], st["slots"])
        write_json_atomic(pools_path(cfg), st)
    return {"changed": len(previous)}


def rename_slot(cfg: Config, slot_id: str, name: str) -> dict:
    if not name.strip():
        raise ApiError(400, "slot name is empty")
    with STATE_LOCK:
        st = _state(cfg)
        if slot_id not in st["slots"]:
            raise ApiError(404, f"no slot {slot_id!r}")
        st["slots"][slot_id].update(name=name.strip(), renamed=True)
        if slot_id in st.get("custom_slots", {}):
            st["custom_slots"][slot_id].update(name=name.strip(), renamed=True)
        write_json_atomic(pools_path(cfg), st)
        return st["slots"][slot_id]


def merge_slot(cfg: Config, src: str, dst: str) -> dict:
    with STATE_LOCK:
        st = _state(cfg)
        if src == dst or src not in st["slots"] or dst not in st["slots"]:
            raise ApiError(400, "merge needs two different existing slots")
        guids = [g for g, r in st["routes"].items() if r["to"] == "slot" and r.get("slot") == src]
        for g in guids:
            st["routes"][g]["slot"] = dst
        merged = st.setdefault("merged", {})
        repointed = [k for k, v in merged.items() if v == src]
        for k in repointed:
            merged[k] = dst
        merged[src] = dst
        st.setdefault("merge_undo", {})[src] = {"into": dst, "guids": guids, "slot": dict(st["slots"][src]), "repointed": repointed}
        del st["slots"][src]                        # its manifest entry stays: the studio never deletes
        _count_lines(st["routes"], st["slots"])
        write_json_atomic(pools_path(cfg), st)
    return {"changed": len(guids)}


def unmerge_slot(cfg: Config, src: str) -> dict:
    """Undo merge_slot: bring the slot back and move the lines it owned (that are still in the target) home."""
    with STATE_LOCK:
        st = _state(cfg)
        rec = (st.get("merge_undo") or {}).get(src)
        if rec is None or src not in (st.get("merged") or {}):
            raise ApiError(404, f"no recorded merge for slot {src!r}")
        dst = rec["into"]
        if dst not in st["slots"]:
            raise ApiError(400, f"the target slot {dst!r} no longer exists; unmerge it first")
        st["slots"][src] = dict(rec["slot"])
        moved = 0
        for g in rec["guids"]:
            r = st["routes"].get(g)
            if r and r["to"] == "slot" and r.get("slot") == dst:
                r["slot"] = src
                moved += 1
        for k in rec.get("repointed", []):
            st["merged"][k] = src
        del st["merged"][src]
        del st["merge_undo"][src]
        _count_lines(st["routes"], st["slots"])
        write_json_atomic(pools_path(cfg), st)
        return {"changed": moved, "slot": st["slots"][src]}


def _slot_id(name: str) -> str:
    sid = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not sid:
        raise ApiError(400, "slot name needs at least one letter or digit")
    return "custom_" + sid


def create_slot(cfg: Config, body: dict) -> dict:
    """A hand-made designed voice ('New designed voice...'). Stored in custom_slots so rebuild keeps it."""
    name = (body.get("name") or "").strip()
    gender = (body.get("gender") or "").strip().lower()
    species = (body.get("species") or "human").strip().lower()
    age = (body.get("age") or "").strip().lower() or None
    if not name:
        raise ApiError(400, "slot name is empty")
    if gender not in ("male", "female", "any"):
        raise ApiError(400, "gender must be male, female or any")
    sid = _slot_id(name)
    with STATE_LOCK:
        st = _state(cfg)
        key = SLOT_PREFIX + sid
        if sid in st["slots"] or sid in (st.get("merged") or {}) or key in read_json(cfg.voice_design / "design_manifest.json", {}):
            raise ApiError(409, f"a voice called {name!r} already exists")
        rec = {"id": sid, "name": name, "speaker_key": key, "gender": gender, "species": species, "age": age, "lines": 0,
               "custom": True, "renamed": True}
        if body.get("description"):
            rec["description"] = str(body["description"])
        st["slots"][sid] = rec
        st.setdefault("custom_slots", {})[sid] = dict(rec)
        write_json_atomic(pools_path(cfg), st)
        ensure_slot_speakers(cfg, {sid: rec})
    by_name = {s["name"]: s["slug"] for s in speakers.list_speakers(cfg)}
    return {**rec, "slug": by_name.get(key, key), "spot": {"checked": 0, "wrong": 0}}


def spot_check_sample(cfg: Config, slot_id: str, seed=None) -> dict:
    st = _state(cfg)
    if slot_id not in st["slots"]:
        raise ApiError(404, f"no slot {slot_id!r}")
    spot = st.get("spot", {}).get(slot_id, {"checked": 0, "wrong": 0})
    size = SPOT_CHECK_LINES * (2 if spot["wrong"] else 1)
    pool = sorted(g for g, r in st["routes"].items()
                  if r["to"] == "slot" and r.get("slot") == slot_id and r["source"] == "auto" and not r.get("checked"))
    pick = random.Random(seed).sample(pool, min(size, len(pool)))
    text = {j["guid"]: j["text"] for j in _unnamed_jobs(cfg)}
    return {"slot": slot_id, "size": size, "remaining": len(pool),
            "items": [{"guid": g, "text": text.get(g, ""), "entry": st["routes"][g]["entry"], "wav": _wav(cfg, g)} for g in pick]}


def record_spot_check(cfg: Config, slot_id: str, results: dict) -> dict:
    with STATE_LOCK:
        st = _state(cfg)
        if slot_id not in st["slots"]:
            raise ApiError(404, f"no slot {slot_id!r}")
        spot = st.setdefault("spot", {}).setdefault(slot_id, {"checked": 0, "wrong": 0})
        for g, ok in results.items():
            r = st["routes"].get(g)
            if r is None or r.get("slot") != slot_id:
                continue
            r["checked"] = True
            spot["checked"] += 1
            if not ok:
                spot["wrong"] += 1
                r["reasons"] = sorted(set(r["reasons"]) | {"spot-check failed"})
        write_json_atomic(pools_path(cfg), st)
        return dict(spot)
