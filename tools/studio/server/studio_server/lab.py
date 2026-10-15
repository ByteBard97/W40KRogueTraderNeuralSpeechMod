"""Render lab: take one cast speaker's lines, change how the text is prepared and how the model is run, listen, compare.

A recipe is the whole experiment: model options (cfg, steps, ...), the style prefix, pronunciation overrides, what each punctuation
mark becomes, how the text is split and how long the silences between pieces are. The same recipe renders any line; a take keeps the
recipe it was made with, so two takes of one line can always be compared. Everything lives under data/studio/lab/<speaker>/.
The model is the shared live_backend (one generation at a time); batches run on a background thread and report progress.
"""
from __future__ import annotations

import copy
import json
import random
import re
import threading
import time
from pathlib import Path
from urllib.parse import unquote

from . import lab_audio, lab_text
from .processed_steps import steps_for
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

CAST_JOBS = "jobs_cast_all.jsonl"
CAST_WAV = "wav"
DEFAULT_RECIPE = {
    "name": "production (as rendered)", "cfg": 3.0, "timesteps": 10, "normalize": False, "retry_badcase": False, "retry_ratio": None,
    "instruct": "annotation", "instruct_text": "", "clean": True, "lexicon": True, "pronunciation": [],
    "punctuation": dict(lab_text.DEFAULT_PUNCT), "pause_ms": lab_text.DEFAULT_PAUSE_MS, "gaps_ms": dict(lab_text.DEFAULT_GAPS_MS),
    "split": {"mode": "whole", "max_chars": 1200, "min_chars": 0}, "seed": "", "peak_limit_db": -1.0,
    "level_match": False, "trim_silence": False, "onset_soften_db": 0.0, "onset_soften_ms": 150,
}
MAX_SEEDS = 6
MAX_ITEMS = 400
RATING_MAX = 5
_JOBS: dict[str, dict] = {}
_JOB_LOCK = threading.Lock()
_CACHE: dict = {"mtime": None, "by_speaker": {}}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def lab_dir(cfg: Config, speaker: str) -> Path:
    return cfg.studio / "lab" / slug(speaker)


# ---- the speaker's lines ------------------------------------------------------------------------------------------------
EXTRA_LINES = "extra_lines.jsonl"      # data/studio/lab/: hand-picked lines of any speaker (e.g. a sample of flagged narrator clips)


def _line_row(j: dict, n: int) -> dict:
    return {"guid": j["guid"], "cue": j["parent"], "seg_index": j.get("seg_index", 0), "order": n, "text": j["text"],
            "src_text": j.get("src_text", ""), "chars": len(j["text"]), "ref": j["ref"], "annotation": j.get("annotation") or {},
            "kind": j.get("speaker_kind"), "current_wav": j.get("current_wav"), "scan": j.get("scan")}


def _cast_lines(cfg: Config) -> dict[str, list[dict]]:
    path = cfg.render / CAST_JOBS
    extra = cfg.studio / "lab" / EXTRA_LINES
    stamp = (path.stat().st_mtime if path.is_file() else 0, extra.stat().st_mtime if extra.is_file() else 0)
    if not path.is_file() and not extra.is_file():
        return {}
    m = stamp
    if _CACHE["mtime"] != m:
        by: dict[str, list[dict]] = {}
        for n, ln in enumerate(path.read_text(encoding="utf-8").splitlines() if path.is_file() else []):
            j = json.loads(ln)
            if j.get("seg_kind", "speech") != "speech" or j["speaker"] == "narrator":
                continue
            by.setdefault(j["speaker"], []).append(_line_row(j, n))
        for n, ln in enumerate(extra.read_text(encoding="utf-8").splitlines() if extra.is_file() else []):
            j = json.loads(ln)
            by.setdefault(j["speaker"], []).append(_line_row(j, n))
        _CACHE.update(mtime=m, by_speaker=by)
    return _CACHE["by_speaker"]


def speakers(cfg: Config) -> list[dict]:
    rows = [{"speaker": s, "slug": slug(s), "lines": len(v), "chars": sum(x["chars"] for x in v)} for s, v in _cast_lines(cfg).items()]
    return sorted(rows, key=lambda r: -r["lines"])


def canon(cfg: Config, speaker: str) -> str:
    """The cast speaker's real name from a name, a %-encoded name or a slug (URLs carry the slug)."""
    speaker = unquote(speaker or "")
    for name in _cast_lines(cfg):
        if speaker == name or speaker == slug(name):
            return name
    raise ApiError(404, f"no cast lines for {speaker!r}")


def _speaker_lines(cfg: Config, speaker: str) -> list[dict]:
    lines = _cast_lines(cfg).get(canon(cfg, speaker))
    if lines is None:
        raise ApiError(404, f"no cast lines for {speaker!r}")
    return lines


def lines(cfg: Config, speaker: str) -> dict:
    """The speaker's lines with the metrics of the take already in the render (cached by guid)."""
    speaker = canon(cfg, speaker)
    cache_path = cfg.studio / "lab" / "metrics_cache.json"
    cache = read_json(cache_path, {})
    out, dirty = [], False
    for ln in _speaker_lines(cfg, speaker):
        m = cache.get(ln["guid"])
        rel = ln.get("current_wav") or f"data/render/cast/{CAST_WAV}/{ln['guid']}.wav"
        wav = cfg.root / rel
        if m is None and wav.is_file():
            x, sr = lab_audio.read_wav(wav)
            m = cache[ln["guid"]] = lab_audio.metrics(x, sr)
            dirty = True
        out.append({**ln, "current": {"wav": rel, **(m or {})} if m else None,
                    "instruct": ln["annotation"].get("instruct")})
    if dirty:
        write_json_atomic(cache_path, cache)
    return {"speaker": speaker, "lines": out, "ref": out[0]["ref"] if out else None}


# ---- recipes ------------------------------------------------------------------------------------------------------------
def check_recipe(r: dict | None) -> dict:
    """The recipe with defaults filled in and every value checked; raises ApiError(400) for a bad one."""
    out = copy.deepcopy(DEFAULT_RECIPE)
    for k, v in (r or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k].update(v)
        elif k in out:
            out[k] = v
    for k in ("cfg", "timesteps"):
        if isinstance(out[k], bool) or not isinstance(out[k], (int, float)) or out[k] <= 0:
            raise ApiError(400, f"{k} must be a positive number, got {out[k]!r}")
    seed = str(out.get("seed", "")).strip()
    if seed and not seed.isdigit():
        raise ApiError(400, f"seed must be blank or a whole number, got {seed!r}")
    for k, lo, hi in (("onset_soften_db", -24.0, 0.0), ("onset_soften_ms", 10, 1000)):
        if isinstance(out[k], bool) or not isinstance(out[k], (int, float)) or not lo <= out[k] <= hi:
            raise ApiError(400, f"{k} must be a number from {lo} to {hi}, got {out[k]!r}")
    if out["instruct"] not in ("annotation", "none", "custom"):
        raise ApiError(400, f"instruct must be annotation, none or custom, got {out['instruct']!r}")
    if out["split"].get("mode") not in lab_text.SPLIT_MODES:
        raise ApiError(400, f"split mode must be one of {lab_text.SPLIT_MODES}")
    for mark, action in out["punctuation"].items():
        if mark not in lab_text.MARKS or action not in lab_text.ACTIONS:
            raise ApiError(400, f"punctuation {mark!r}: {action!r} is not allowed")
    for o in out["pronunciation"]:
        if o.get("mode", "arpabet") not in ("arpabet", "plain", "literal"):
            raise ApiError(400, f"pronunciation mode must be arpabet, plain or literal, got {o.get('mode')!r}")
    return out


def options() -> dict:
    return {"default_recipe": DEFAULT_RECIPE, **lab_text.punct_options()}


def recipes(cfg: Config) -> list[dict]:
    return [DEFAULT_RECIPE, *read_json(cfg.studio / "lab" / "recipes.json", [])]


def save_recipe(cfg: Config, body: dict) -> list[dict]:
    r = check_recipe(body.get("recipe"))
    name = str(body.get("name") or r.get("name") or "").strip()
    if not name:
        raise ApiError(400, "a recipe needs a name")
    r["name"] = name
    path = cfg.studio / "lab" / "recipes.json"
    with STATE_LOCK:
        saved = [x for x in read_json(path, []) if x["name"] != name]
        write_json_atomic(path, saved + [r])
    return recipes(cfg)


# ---- text -> pieces -----------------------------------------------------------------------------------------------------
def prepare(cfg: Config, body: dict) -> dict:
    r = check_recipe(body.get("recipe"))
    text = body.get("text")
    if body.get("guid"):
        text = next((x["text"] for x in _speaker_lines(cfg, body["speaker"]) if x["guid"] == body["guid"]), None)
        if text is None:
            raise ApiError(404, "unknown line")
    if not text:
        raise ApiError(400, "text or guid is required")
    return {**lab_text.prepare(text, r), "recipe": r}


def lexicon_lookup(q: str) -> list[dict]:
    from phonemes import phonemize
    import lexicon
    entries, _ = lexicon._load()
    q = (q or "").lower().strip()
    hits = [k for k in entries if q in k] if q else []
    return [{"word": k, "ipa": entries[k].get("ipa"), "respell": entries[k].get("respell"), "arpabet": entries[k].get("arpabet"),
             "voxcpm2": entries[k].get("voxcpm2"), "as_sent": phonemize(k)} for k in sorted(hits)[:30]]


# ---- takes --------------------------------------------------------------------------------------------------------------
def _takes_path(cfg: Config, speaker: str) -> Path:
    return lab_dir(cfg, speaker) / "takes.json"


def takes(cfg: Config, speaker: str, guid: str | None = None) -> list[dict]:
    speaker = canon(cfg, speaker)
    rows = [t for t in read_json(_takes_path(cfg, speaker), {}).values() if not t.get("hidden") and (not guid or t.get("guid") == guid)]
    return sorted(rows, key=lambda t: t["id"], reverse=True)


def update_take(cfg: Config, speaker: str, take_id: str, body: dict) -> dict:
    speaker = canon(cfg, speaker)
    with STATE_LOCK:
        all_ = read_json(_takes_path(cfg, speaker), {})
        if take_id not in all_:
            raise ApiError(404, "unknown take")
        t = all_[take_id]
        if "rating" in body:
            if not isinstance(body["rating"], int) or not 0 <= body["rating"] <= RATING_MAX:
                raise ApiError(400, f"rating must be an integer 0 to {RATING_MAX}")
            t["rating"] = body["rating"]
        if "note" in body:
            t["note"] = str(body["note"])
        if "hidden" in body:                 # hiding is the only removal: the audio stays on disk
            t["hidden"] = bool(body["hidden"])
        write_json_atomic(_takes_path(cfg, speaker), all_)
    return t


def _instruct(recipe: dict, line: dict | None) -> str | None:
    return lab_text.instruct_for(recipe, (line or {}).get("annotation"))


def _render_one(cfg: Config, model, speaker: str, item: dict, recipe: dict, seed: int, ref: dict, line: dict | None, check) -> dict:
    prep = lab_text.prepare(item["text"], recipe)
    chunks, gaps, spoken = [], [], []
    for i, piece in enumerate(prep["pieces"]):
        check()
        req = {"text": piece["text"], "reference_wav": ref["wav"], "seed": seed + i, "cfg": recipe["cfg"], "timesteps": steps_for(cfg, speaker, recipe["timesteps"]),
               "retry_badcase": recipe["retry_badcase"], "normalize": recipe["normalize"]}
        if recipe.get("retry_ratio"):
            req["retry_badcase_ratio_threshold"] = recipe["retry_ratio"]
        instruct = _instruct(recipe, line)
        if instruct:
            req["instruct"] = instruct
        r = model.call("/generate", req)
        x, sr = lab_audio.read_wav(cfg.voice_design / r["file"])
        chunks.append(x)
        gaps.append(piece["gap_ms"] or 0)
        lvl = lab_audio.speech_level_db(x, sr)
        spoken.append({"text": piece["text"], "level_db": None if lvl is None else round(lvl, 1),
                       **{k: v for k, v in lab_audio.metrics(x, sr).items() if k in ("seconds", "crest_db", "flag")}})
    if recipe.get("trim_silence"):
        chunks = [lab_audio.trim_silence(c, sr) for c in chunks]
    if recipe.get("level_match"):
        chunks = lab_audio.match_levels(chunks, sr)
    if float(recipe.get("onset_soften_db") or 0) < 0:                   # only pieces that follow another one start "mid-speech"
        chunks = [c if i == 0 else lab_audio.soften_onset(c, sr, float(recipe["onset_soften_db"]), int(recipe["onset_soften_ms"])) for i, c in enumerate(chunks)]
    over = max((float(abs(c).max()) for c in chunks), default=0.0)       # >1.0: the model went past full scale (a 16-bit write would clip it)
    audio = lab_audio.limit_peak(lab_audio.join(chunks, gaps, sr), recipe.get("peak_limit_db"))
    take_id = f"t{int(time.time() * 1000)}{random.randrange(1000):03d}"
    wav = lab_dir(cfg, speaker) / "takes" / f"{take_id}.wav"
    lab_audio.write_wav(wav, audio, sr)
    take = {"id": take_id, "speaker": speaker, "guid": item.get("guid"), "label": item.get("label", ""), "text": item["text"],
            "recipe": recipe, "seed": seed, "ref": ref["wav"], "instruct": _instruct(recipe, line), "pieces": spoken,
            "wav": str(wav.relative_to(cfg.root)), "metrics": {**lab_audio.metrics(audio, sr), "model_peak": round(over, 3)}, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "rating": 0, "note": "", "hidden": False}
    with STATE_LOCK:
        all_ = read_json(_takes_path(cfg, speaker), {})
        all_[take_id] = take
        write_json_atomic(_takes_path(cfg, speaker), all_)
    return take


def start_render(cfg: Config, model, body: dict) -> dict:
    """Queue a batch: every item x every seed with one recipe. Returns the job (poll /api/lab/jobs/<id>)."""
    speaker = canon(cfg, body["speaker"])
    recipe = check_recipe(body.get("recipe"))
    have = {x["guid"]: x for x in _speaker_lines(cfg, speaker)}
    items = []
    for it in body["items"][:MAX_ITEMS]:
        line = have.get(it.get("guid"))
        if not line and not it.get("text"):
            raise ApiError(400, f"item needs a known guid or text: {it}")
        items.append({"guid": it.get("guid"), "label": it.get("label", ""), "text": it.get("text") or line["text"], "line": line,
                      "ref": body.get("ref") or (line or {}).get("ref")})       # each line renders with its own reference clip
    if not items:
        raise ApiError(400, "nothing to render")
    seeds = body.get("seeds") or ([int(recipe["seed"])] if str(recipe["seed"]).strip() else [None])
    seeds = [random.randrange(2 ** 31) if s in (None, "") else int(s) for s in seeds[:MAX_SEEDS]]
    for it in items:
        if not it["ref"] or cfg.under_data(it["ref"]["wav"]) is None:
            raise ApiError(400, "a reference clip under data/ is required (ref.wav)")
    job = {"id": f"lj{int(time.time() * 1000)}", "speaker": speaker, "state": "queued", "total": len(items) * len(seeds), "done": 0,
           "take_ids": [], "error": None, "cancel": False, "started": time.strftime("%H:%M:%S")}
    with _JOB_LOCK:
        _JOBS[job["id"]] = job

    def check():
        if job["cancel"]:
            raise InterruptedError("cancelled")

    def run():
        job["state"] = "running"
        try:
            for it in items:
                for seed in seeds:
                    check()
                    take = _render_one(cfg, model, speaker, it, recipe, seed, it["ref"], it["line"], check)
                    job["take_ids"].append(take["id"])
                    job["done"] += 1
            job["state"] = "done"
        except InterruptedError:
            job["state"] = "cancelled"
        except Exception as e:                  # the page shows the message; a half-finished batch keeps its takes
            job.update(state="error", error=f"{type(e).__name__}: {e}"[:300])

    threading.Thread(target=run, daemon=True).start()
    return {k: v for k, v in job.items() if k != "cancel"}


def get_job(job_id: str) -> dict:
    j = _JOBS.get(job_id)
    if j is None:
        raise ApiError(404, "unknown job")
    return {k: v for k, v in j.items() if k != "cancel"}


def cancel_job(job_id: str) -> dict:
    j = _JOBS.get(job_id)
    if j is None:
        raise ApiError(404, "unknown job")
    j["cancel"] = True
    return get_job(job_id)


def active_jobs() -> list[dict]:
    return [{k: v for k, v in j.items() if k != "cancel"} for j in _JOBS.values() if j["state"] in ("queued", "running")]


REAL_CLIP_LIMIT = 12
_REAL: dict = {}


def real_clips(cfg: Config, q: str, limit: int = REAL_CLIP_LIMIT) -> list[dict]:
    """The game's own voice clips whose text contains `q` (shortest first), for matching how a word is really said."""
    q = (q or "").strip().lower()
    if len(q) < 3:
        return []
    path = cfg.voices / "catalog.json"
    if not path.is_file():
        return []
    if _REAL.get("mtime") != path.stat().st_mtime:
        _REAL.update(mtime=path.stat().st_mtime, rows=json.loads(path.read_text(encoding="utf-8")))
    hits = []
    for v in _REAL["rows"].values():
        for t in v.get("texts", []):
            if q in t["text"].lower() and v.get("speaker") != "_unattributed":
                hits.append({"speaker": v["speaker"], "wav": f"data/voices/{v['wav']}", "seconds": round(v.get("duration", 0), 1), "text": t["text"]})
                break
    hits.sort(key=lambda h: len(h["text"]))          # the shortest sentence first: the word is most of what you hear
    return hits[: max(1, int(limit))]
