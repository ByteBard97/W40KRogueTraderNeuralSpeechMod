from __future__ import annotations

import sys

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .speakers import find_speaker, list_speakers

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[4] / "tools/voice_design"))
from audit_server import apply_order, apply_verdict, keep_candidate  # noqa: E402  (pure helpers, already tested)
from register import register as register_picks  # noqa: E402  (copies picks into the prompt bank, already tested)


def design_name(cfg: Config, slug: str) -> str:
    sp = find_speaker(cfg, slug)
    if sp["origin"] != "designed":
        raise ApiError(404, f"'{sp['name']}' has no designed voice")
    return sp["name"]


def _manifest(cfg: Config) -> dict:
    return read_json(cfg.voice_design / "design_manifest.json", {})


def post_verdict(cfg: Config, slug: str, body: dict) -> dict:
    name = design_name(cfg, slug)
    if body.get("cand") not in _manifest(cfg)[name]["candidates"]:
        raise ApiError(400, f"unknown candidate {body.get('cand')!r}")
    with STATE_LOCK:
        audit = read_json(cfg.voice_design / "audit.json", {})
        write_json_atomic(cfg.voice_design / "audit.json", apply_verdict(audit, {**body, "name": name}))
    return {}


def post_order(cfg: Config, slug: str, order: list[str]) -> dict:
    name = design_name(cfg, slug)
    known = set(_manifest(cfg)[name]["candidates"])
    if any(c not in known for c in order):
        raise ApiError(400, "order contains an unknown candidate")
    with STATE_LOCK:
        audit = read_json(cfg.voice_design / "audit.json", {})
        write_json_atomic(cfg.voice_design / "audit.json", apply_order(audit, {"name": name, "order": order}))
    return {}


def post_description(cfg: Config, slug: str, description: str) -> dict:
    name = design_name(cfg, slug)
    if not description.strip():
        raise ApiError(400, "description is empty")
    with STATE_LOCK:
        ov = read_json(cfg.voice_design / "overrides.json", {})
        ov[name] = description
        write_json_atomic(cfg.voice_design / "overrides.json", ov)
    return {}


def keep(cfg: Config, slug: str, body: dict) -> dict:
    name = design_name(cfg, slug)
    rel = body.get("file", "")
    tmp = (cfg.voice_design / rel).resolve() if rel and not rel.startswith("/") else None
    live = (cfg.voice_design / "live_tmp").resolve()
    if tmp is None or live not in tmp.parents or not tmp.is_file():
        raise ApiError(400, f"not a live take: {rel!r}")
    with STATE_LOCK:
        manifest = _manifest(cfg)
        for cand_id, g in (manifest[name].get("gen") or {}).get("candidates", {}).items():
            if g.get("live_file") == rel:        # a double-click on Keep must not make a second identical candidate
                return {"cand": cand_id}
        # Every kept candidate must be regenerable, so description and text are always recorded: take them from the
        # request when sent, otherwise from the speaker's saved description and sample sentence.
        description = body.get("description") or read_json(cfg.voice_design / "overrides.json", {}).get(name, manifest[name]["description"])
        rec = {"description": description, "text": body.get("text") or manifest[name]["text"], "live_file": rel}
        for k in ("seed", "cfg", "timesteps"):
            if k not in body:
                raise ApiError(400, f"keep needs '{k}' so the candidate can be regenerated")
            rec[k] = body[k]
        cand = keep_candidate(manifest, name, tmp, rec, vd=cfg.voice_design)
        write_json_atomic(cfg.voice_design / "design_manifest.json", manifest)
    return {"cand": cand}


def register_pick(cfg: Config, slug: str) -> dict:
    name = design_name(cfg, slug)
    with STATE_LOCK:
        audit = read_json(cfg.voice_design / "audit.json", {})
        pick = (audit.get(name) or {}).get("pick")
        if not pick:
            raise ApiError(400, f"'{name}' has no pick yet; rank a candidate first")
        if pick not in _manifest(cfg)[name]["candidates"]:
            raise ApiError(400, f"the pick {pick!r} is not one of {name}'s candidates")
        if ((audit[name].get("cands") or {}).get(pick) or {}).get("reject"):
            raise ApiError(409, f"the pick {pick!r} is marked rejected; clear that or pick another")
        pj = cfg.voices / "prompts/prompts.json"
        prompts = read_json(pj, {})
        done = register_picks({name: audit[name]}, _manifest(cfg), prompts, vd_root=cfg.voice_design,
                              voices_root=cfg.voices)
        if not done:
            raise ApiError(409, f"the picked clip for '{name}' is missing, nothing was registered")
        write_json_atomic(pj, prompts)
    return {"registered": done}


def register_all(cfg: Config) -> dict:
    """Register every designed speaker's pick, one at a time with the per-speaker checks; failures are reported, not fatal."""
    registered, skipped = [], []
    for s in list_speakers(cfg):
        if s["origin"] != "designed" or not s["has_pick"]:
            continue
        try:
            registered.extend(register_pick(cfg, s["slug"])["registered"])
        except ApiError as e:
            skipped.append({"name": s["name"], "reason": e.message})
    return {"registered": registered, "skipped": skipped}


def generate(cfg: Config, model, slug: str, body: dict) -> dict:
    name = design_name(cfg, slug)
    m = _manifest(cfg)[name]
    description = body.get("description") or read_json(cfg.voice_design / "overrides.json", {}).get(name, m["description"])
    r = model.call("/generate", {"description": description, "text": m["text"], "seed": body.get("seed", ""),
                                 "cfg": body.get("cfg", 2.0), "timesteps": body.get("timesteps", 10)})
    return {**r, "description": description, "text": m["text"]}
