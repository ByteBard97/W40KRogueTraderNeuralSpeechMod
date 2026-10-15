"""Casting: give the characters that have no voice a real voice from the BG3 catalog.

Characters come from data/npc_profile/describe/casting_needs.json (sorted by line count, the "screen time"), BG3 voices from
data/bg3_voices/catalog.json. Assignments and portrait corrections live in data/studio/casting.json. Registering copies the chosen
BG3 reference clip into data/voices/prompts/cast/ and adds the character to prompts.json, which is where plan_voiceless.py looks
first, so the next render uses the cast voice.
"""
from __future__ import annotations

import difflib
import json
import re
import shutil
import time
import wave
from pathlib import Path

from . import bg3_labels
from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

SUGGESTIONS = 6                       # candidates offered per character
UNUSED_BONUS = 0.15                   # a voice nobody has been cast as is preferred
NON_HUMAN = {"machine", "necron", "daemon", "mutant", "xenos_other", "unknown", "mixed"}
AUDITION_MIN_CHARS, AUDITION_MAX_CHARS = 60, 240
SAMPLE_LINES = 3
# Names a BG3 character is better known by than the one the game data shows (searched, and shown next to the name).
ALIASES = {"nightsong": ["Dame Aylin", "Aylin"], "the emperor": ["Dream Visitor"], "dream visitor": ["The Emperor"],
           "lord enver gortash": ["Gortash", "Enver Gortash"]}
SLOT_RANK_FRACTION = 0.5               # nameless groups are offered middle-of-the-list voices, not the iconic ones
NOT_CASTABLE = {"narrator"}          # already the narrator of the whole mod
PORTRAIT_CUTOFF = 0.8
MIN_TOKEN = 5


def _paths(cfg: Config) -> dict[str, Path]:
    d = cfg.data
    return {"needs": d / "npc_profile/describe/casting_needs.json", "in": d / "npc_profile/describe/in",
            "catalog": d / "bg3_voices/catalog.json", "state": cfg.studio / "casting.json",
            "portraits": d / "portraits/half", "prompts": cfg.voices / "prompts/prompts.json",
            "cast": cfg.voices / "prompts/cast", "auditions": cfg.studio / "casting/auditions"}


def _need(path: Path, what: str):
    if not path.is_file():
        raise ApiError(404, f"{what} not found ({path.name}); run the casting prep first")
    return read_json(path, None)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def portrait_names(cfg: Config) -> list[str]:
    p = _paths(cfg)["portraits"]
    return sorted(f.stem for f in p.glob("*.png")) if p.is_dir() else []


def guess_portrait(speaker: str, names: list[str]) -> str | None:
    """Best portrait file stem for a character name: exact, then a long shared token, then a close spelling of any long word."""
    idx = {_norm(n): n for n in names}
    key = _norm(speaker)
    if key in idx:
        return idx[key]
    toks = [t for t in (_norm(t) for t in re.split(r"[\s\-]+", speaker)) if len(t) >= MIN_TOKEN]
    for tok in toks:
        for k, v in idx.items():
            if tok in k or (len(k) >= MIN_TOKEN and k in tok):
                return v
    for tok in toks + [key]:
        close = difflib.get_close_matches(tok, list(idx), n=1, cutoff=PORTRAIT_CUTOFF)
        if close:
            return idx[close[0]]
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def state(cfg: Config) -> dict:
    s = read_json(_paths(cfg)["state"], {})
    s.setdefault("assignments", {})
    s.setdefault("portraits", {})
    return s


_TEXTS: dict = {"stamp": None, "by": {}}


def _job_texts(cfg: Config) -> dict[str, list[str]]:
    """Spoken text per speaker from the job list (named speakers, plus unnamed cues routed to a speaker in the Voice Studio pools)."""
    path = cfg.render / "jobs.jsonl"
    if not path.is_file():
        return {}
    stamp = (path.stat().st_mtime, path.stat().st_size)
    if _TEXTS["stamp"] != (str(path), stamp):
        routes = (read_json(cfg.studio / "pools.json", {}) or {}).get("routes", {})
        by: dict[str, list[str]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            j = json.loads(line)
            sp = j["speaker"]
            if j.get("speaker_kind") == "default_speaker":
                r = routes.get(j["guid"])
                sp = r.get("speaker") if r and r.get("to") == "speaker" else (f"pool_{r['slot']}" if r and r.get("to") == "slot" else None)
            if sp and j.get("text"):
                by.setdefault(sp, []).append(j["text"])
        _TEXTS.update(stamp=(str(path), stamp), by=by)
    return _TEXTS["by"]


def _samples(cfg: Config) -> dict[str, list[str]]:
    """Sample lines per speaker: the description pass's lines first, then lines of a speakable length from the job list."""
    out: dict[str, list[str]] = {}
    for f in sorted(_paths(cfg)["in"].glob("batch_*.json")):
        for r in read_json(f, []):
            out[r["speaker"]] = [x["text"] for x in r.get("sample_lines", [])]
    for sp, texts in _job_texts(cfg).items():
        fit = [t for t in texts if AUDITION_MIN_CHARS <= len(t) <= AUDITION_MAX_CHARS]
        if fit:
            out[sp] = fit[:: max(1, len(fit) // SAMPLE_LINES)][:SAMPLE_LINES] + [t for t in out.get(sp, []) if t not in fit]
    return out


def _designed_info(cfg: Config) -> dict[str, dict]:
    return read_json(cfg.voice_design / "design_manifest.json", {}) or {}


def eligible(catalog: list[dict], species: str | None, gender: str | None) -> list[dict]:
    """BG3 voices that could play this character: have a clip, fit the gender, and are (not) a creature voice."""
    human = species not in NON_HUMAN
    out = []
    for v in catalog:
        if not v.get("refs") or v.get("lines", 0) < 30 or v.get("refs_quality") == "poor":    # a reference with too little speech clones badly
            continue
        name = (v.get("name") or "").lower()
        if name in NOT_CASTABLE or (human and (v.get("non_human_hint") or "player voice" in name)):
            continue
        if human and gender in ("male", "female") and v.get("gender") not in (gender, "unclear"):
            continue
        out.append(v)
    return sorted(out, key=lambda v: -v["lines"])


def _voice_name(v: dict) -> str:
    """Eight catalog speakers have no resolved name; show their technical name rather than nothing."""
    return v.get("name") or v.get("tech_name") or v["slug"]


def tech_alias(v: dict) -> str | None:
    """The character name inside a technical name ('S_GLO_Elminster' -> 'Elminster'), when it differs from the shown name."""
    last = (v.get("tech_name") or "").split("_")[-1]
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", last).strip()
    if _norm(words) in ("male", "female") or len(_norm(words)) < MIN_TOKEN - 1 or _norm(words) == _norm(_voice_name(v)) or _norm(words) in _norm(_voice_name(v)):
        return None
    return words


def aliases(v: dict) -> list[str]:
    out = list(ALIASES.get(_voice_name(v).lower(), []))
    t = tech_alias(v)
    if t and t.lower() not in (a.lower() for a in out):
        out.append(t)
    return out


def used_by(cfg: Config) -> dict[str, list[str]]:
    """BG3 voice slug -> every character cast as it, the one with the most lines first."""
    lines = {r["speaker"]: r["lines"] for r in targets(cfg)}
    out: dict[str, list[str]] = {}
    for sp, a in state(cfg)["assignments"].items():
        out.setdefault(a["bg3"], []).append(sp)
    return {slug: sorted(sps, key=lambda x: -lines.get(x, 0)) for slug, sps in out.items()}


def suggest(rank_fraction: float, pool: list[dict], used: dict[str, list[str]], n: int = SUGGESTIONS) -> list[dict]:
    """Pair big with big: a character near the top of the screen-time list is offered BG3 voices near the top of the pool."""
    if not pool:
        return []
    target = rank_fraction * (len(pool) - 1)
    scored = []
    for i, v in enumerate(pool):
        score = -abs(i - target) / max(1, len(pool) - 1) + (UNUSED_BONUS if v["slug"] not in used else 0.0)
        scored.append((score, -v["lines"], v))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [{"slug": v["slug"], "name": _voice_name(v), "lines": v["lines"], "gender": v["gender"],
             "f0": v.get("median_f0_hz"), "used_by": used.get(v["slug"], [])} for _, _, v in scored[:n]]


def page(cfg: Config) -> dict:
    p = _paths(cfg)
    needs = targets(cfg)
    n_named = sum(1 for r in needs if r["kind"] == "character")
    catalog = _need(p["catalog"], "BG3 catalog")
    st = state(cfg)
    names = portrait_names(cfg)
    samples = _samples(cfg)
    designed = _designed_info(cfg)
    by_slug = {v["slug"]: v for v in catalog}
    used = used_by(cfg)
    chars = []
    for i, r in enumerate(needs):
        sp = r["speaker"]
        named = r["kind"] == "character"
        rank = i if named else None
        d = designed.get(sp) or {}
        r = {**r, "gender": r.get("gender") or (d.get("gender") or "").lower() or None, "role": r.get("role") or d.get("role"),
             "voice_description": r.get("voice_description") or d.get("description")}
        asg = st["assignments"].get(sp)
        pic = st["portraits"].get(sp) or guess_portrait(sp, names)
        text = [t for t in samples.get(sp, []) if AUDITION_MIN_CHARS <= len(t)][:SAMPLE_LINES] or samples.get(sp, [])[:SAMPLE_LINES]
        chars.append({**r, "display": r.get("display") or sp, "rank": rank + 1 if named else None, "samples": text,
                      "portrait": f"data/portraits/half/{pic}.png" if pic else None, "portrait_name": pic,
                      "portrait_chosen": sp in st["portraits"],
                      "assignment": ({"bg3": asg["bg3"], "name": _voice_name(by_slug[asg["bg3"]])} if asg and asg["bg3"] in by_slug else None),
                      "suggestions": suggest(rank / max(1, n_named - 1) if named else SLOT_RANK_FRACTION,
                                             eligible(catalog, r.get("species"), r.get("gender")), used)})
    return {"characters": chars, "total": len(chars), "assigned": sum(1 for c in chars if c["assignment"]), "portraits": names}


def bg3_voices(cfg: Config) -> list[dict]:
    p = _paths(cfg)
    catalog = _need(p["catalog"], "BG3 catalog")
    used = used_by(cfg)
    labels = bg3_labels.read_all(cfg)
    return [{"slug": v["slug"], "name": _voice_name(v), "lines": v["lines"], "minutes": round(v["seconds"] / 60, 1), "gender": v["gender"],
             "f0": v.get("median_f0_hz"), "non_human": bool(v.get("non_human_hint")), "refs": v["refs"], "used_by": used.get(v["slug"], []), "quality": v.get("refs_quality"),
             "aliases": aliases(v), "labels": bg3_labels.effective(v, labels.get(v["slug"], {})), "mine": labels.get(v["slug"], {}),
             "complete": bg3_labels.is_complete(labels.get(v["slug"], {}))}
            for v in catalog if v.get("refs")]


def slot_targets(cfg: Config) -> list[dict]:
    """The nameless speakers: each pool slot (Voice Studio Pools page) is one casting target, so a BG3 voice can be picked for it."""
    pools = read_json(cfg.studio / "pools.json", {}) or {}
    texts = _job_texts(cfg)
    out = []
    for sid, sl in (pools.get("slots") or {}).items():
        key = sl.get("speaker_key") or f"pool_{sid}"
        chars = sum(len(t) for t in texts.get(key, []))
        out.append({"speaker": key, "kind": "slot", "display": sl.get("name", sid), "lines": sl.get("lines") or len(texts.get(key, [])), "chars": chars,
                    "approx_minutes": round(chars / 15 / 60, 1), "status": "slot", "gender": sl.get("gender"), "species": sl.get("species"),
                    "age": sl.get("age"), "role": f"Nameless speakers: {sl.get('name', sid)}", "voice_description": sl.get("description"),
                    "pool_slot": sid})
    return sorted(out, key=lambda r: -r["lines"])


def targets(cfg: Config) -> list[dict]:
    """Named characters (most lines first) followed by the nameless groups."""
    named = [{**r, "kind": "character"} for r in _need(_paths(cfg)["needs"], "casting_needs.json")]
    return named + slot_targets(cfg)


def _check_speaker(cfg: Config, speaker: str) -> dict:
    for r in targets(cfg):
        if r["speaker"] == speaker:
            return r
    raise ApiError(404, f"unknown character {speaker!r}")


def assign(cfg: Config, speaker: str, bg3: str | None) -> dict:
    _check_speaker(cfg, speaker)
    if bg3 is not None and not any(v["slug"] == bg3 for v in _need(_paths(cfg)["catalog"], "BG3 catalog")):
        raise ApiError(404, f"unknown BG3 voice {bg3!r}")
    with STATE_LOCK:
        st = state(cfg)
        if bg3 is None:
            st["assignments"].pop(speaker, None)
        else:
            st["assignments"][speaker] = {"bg3": bg3, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        write_json_atomic(_paths(cfg)["state"], st)
    return {"speaker": speaker, "bg3": bg3}


def set_portrait(cfg: Config, speaker: str, name: str | None) -> dict:
    _check_speaker(cfg, speaker)
    if name is not None and name not in portrait_names(cfg):
        raise ApiError(404, f"unknown portrait {name!r}")
    with STATE_LOCK:
        st = state(cfg)
        if name is None:
            st["portraits"].pop(speaker, None)
        else:
            st["portraits"][speaker] = name
        write_json_atomic(_paths(cfg)["state"], st)
    return {"speaker": speaker, "portrait": name}


def audition_line(cfg: Config, speaker: str, index: int) -> str:
    lines = [t for t in _samples(cfg).get(speaker, []) if AUDITION_MIN_CHARS <= len(t) <= AUDITION_MAX_CHARS] or _samples(cfg).get(speaker, [])
    if not lines:
        raise ApiError(404, f"no sample line for {speaker!r}")
    return lines[index % len(lines)]


def audition(cfg: Config, model, speaker: str, bg3: str, ref: int = 0, line: int = 0) -> dict:
    """Clone a BG3 reference onto one of the character's real lines so it can be heard before casting."""
    _check_speaker(cfg, speaker)
    voice = next((v for v in _need(_paths(cfg)["catalog"], "BG3 catalog") if v["slug"] == bg3), None)
    if voice is None or not voice.get("refs"):
        raise ApiError(404, f"unknown BG3 voice {bg3!r}")
    clip = voice["refs"][ref % len(voice["refs"])]
    text = audition_line(cfg, speaker, line)
    r = model.call("/generate", {"text": text, "reference_wav": clip["wav"], "seed": "", "cfg": 3.0, "timesteps": 10,
                                 "retry_badcase": False, "normalize": False})
    dest = _paths(cfg)["auditions"] / f"{_slug(speaker)}__{bg3}__{int(time.time())}.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cfg.voice_design / r["file"], dest)
    return {"file": str(dest.relative_to(cfg.root)), "text": text, "seconds": r.get("seconds"), "ref": clip["wav"]}


def _duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return round(w.getnframes() / w.getframerate(), 2)


def register_one(cfg: Config, prompts: dict, catalog: dict[str, dict], speaker: str, bg3: str) -> bool:
    """Put one cast voice into `prompts` (and copy its first reference into the bank). False when the voice has no usable clip."""
    voice = catalog.get(bg3)
    clip = voice["refs"][0] if voice and voice.get("refs") else None
    src = cfg.root / clip["wav"] if clip else None
    if not src or not src.is_file():
        return False
    p = _paths(cfg)
    dst = p["cast"] / f"{_slug(speaker)}.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    prompts[speaker] = [{"rank": 1, "event": f"cast_{_slug(speaker)}", "wav": f"prompts/cast/{_slug(speaker)}.wav",
                         "text": clip["text"], "duration": _duration(dst), "source": f"BG3 voice: {voice['name']}", "bg3": bg3}]
    return True


def register(cfg: Config, only: list[str] | None = None) -> dict:
    """Copy each assigned BG3 reference into the prompt bank under the character's name. Backs prompts.json up first; deletes nothing."""
    p = _paths(cfg)
    catalog = {v["slug"]: v for v in _need(p["catalog"], "BG3 catalog")}
    with STATE_LOCK:
        asg = {sp: a for sp, a in state(cfg)["assignments"].items() if only is None or sp in only}
        prompts = read_json(p["prompts"], {})
        if not asg:
            return {"registered": [], "skipped": []}
        shutil.copyfile(p["prompts"], p["prompts"].with_name(f"prompts.json.pre-casting-{time.strftime('%Y%m%d-%H%M%S')}"))
        done, skipped = [], []
        for speaker, a in asg.items():
            (done if register_one(cfg, prompts, catalog, speaker, a["bg3"]) else skipped).append(speaker)
        write_json_atomic(p["prompts"], prompts)
    return {"registered": done, "skipped": skipped}
