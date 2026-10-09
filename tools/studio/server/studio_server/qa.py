from __future__ import annotations

import glob
import io
import json
import random
import re
import sys
import wave
from pathlib import Path

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

CAP_S = (27.0, 30.2)             # voxcpm2 runs away until its ~30 s generation cap
SLOW_CPS, FAST_CPS = 7.0, 26.0   # characters per second of spoken text; the corpus median is about 15
TYPICAL_CPS = 15.0
SHORT_S = 0.7
VERY_LONG_S = 40.0
MIN_CHARS_FOR_RATE = 8
DEFAULT_LIMIT = 40
MAX_PAGE = 200
EXPORT = "export"
SORTS = ("suspicious", "slowest", "fastest", "longest", "shortest", "random")
VERDICTS = ("good", "bad")
FX_CACHE_MAX = 64

_CLIPS: dict[tuple, tuple[tuple, list[dict]]] = {}
_JOBS: dict[tuple, dict] = {}
_FX: dict[tuple, bytes] = {}


def spoken_text(t: str) -> str:
    return re.sub(r"\{[^}]*\}", "", t).strip()


def auto_flags(dur: float, chars: int, existing: list[str]) -> list[str]:
    """Why a clip looks wrong without listening. `existing` are the flags the render already set."""
    flags = list(existing)
    cps = chars / dur if dur else 0
    if CAP_S[0] <= dur <= CAP_S[1]:
        flags.append("cap_hit")
    if chars >= MIN_CHARS_FOR_RATE and cps < SLOW_CPS:
        flags.append("slow")
    if chars >= MIN_CHARS_FOR_RATE and cps > FAST_CPS:
        flags.append("fast")
    if dur < SHORT_S:
        flags.append("short")
    if dur > VERY_LONG_S:
        flags.append("very_long")
    return flags


def _run_dir(cfg: Config, run: str) -> Path:
    if run == EXPORT:
        return cfg.render / "export"
    d = cfg.render / run
    if not re.fullmatch(r"[\w.\-]+", run) or not (d / "manifest.jsonl").is_file():
        raise ApiError(404, f"no render run {run!r}")
    return d


def _duration(path: Path) -> float | None:
    try:
        with wave.open(str(path)) as w:
            return w.getnframes() / w.getframerate()
    except (OSError, EOFError, wave.Error):
        return None


def _jobs(cfg: Config) -> dict[str, dict]:
    files = sorted(glob.glob(str(cfg.render / "jobs*.jsonl")))
    stamp = tuple((f, Path(f).stat().st_mtime_ns) for f in files)
    if stamp not in _JOBS:
        jobs: dict[str, dict] = {}
        for f in files:
            for ln in open(f, encoding="utf-8"):
                if ln.strip():
                    j = json.loads(ln)
                    jobs[j["guid"]] = j
        _JOBS.clear()
        _JOBS[stamp] = jobs
    return _JOBS[stamp]


def _repo_rel(cfg: Config, p: Path) -> str:
    return str(p.relative_to(cfg.root))


def _export_clips(cfg: Config, d: Path) -> list[dict]:
    index = read_json(d / "index.json", {})
    jobs = _jobs(cfg)
    out = []
    for guid, e in index.items():
        dur = _duration(d / e["wav"])
        if dur is None:
            continue
        j = jobs.get(guid, {})
        text = spoken_text(j.get("text") or e["text"])
        ann = j.get("annotation") or {}
        ref = (j.get("ref") or {}).get("wav", "")
        out.append({
            "guid": guid, "wav": _repo_rel(cfg, d / e["wav"]), "text": text,
            "context": spoken_text(e["text"]) if j.get("text") and spoken_text(e["text"]) != text else "",
            "speaker": e["speaker"], "engine": e["engine"], "voice_source": e.get("voice_source", ""),
            "dur": round(dur, 2), "cps": round(len(text) / dur, 1) if dur else 0,
            "emotion": ann.get("emotion", ""), "instruct": ann.get("instruct", ""),
            "ref_path": ref, "ref": Path(ref).stem if ref else "", "real": [], "old": None, "heard": "", "wer": None,
            "flags": auto_flags(dur, len(text), e.get("flags", [])),
        })
    return out


def _run_clips(cfg: Config, d: Path) -> list[dict]:
    jobs = _jobs(cfg)
    asr = {}
    if (d / "asr.jsonl").exists():
        for ln in open(d / "asr.jsonl", encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                asr[r["guid"]] = r
    real = read_json(d / "real.json", {})
    out = []
    for ln in open(d / "manifest.jsonl", encoding="utf-8"):
        if not ln.strip():
            continue
        r = json.loads(ln)
        guid = r["guid"]
        if r.get("status") != "ok":
            continue
        wav = d / "wav" / f"{guid}.wav"
        dur = _duration(wav)
        if dur is None:
            continue
        j = jobs.get(guid, {})
        text = (r.get("text") or j.get("text", "")).strip()    # exactly what was sent, braced phonemes included
        ref = (j.get("ref") or {}).get("wav", "")
        old = cfg.render / "export/wav" / f"{guid}.wav"
        a = asr.get(guid, {})
        spoken = spoken_text(text)
        out.append({
            "guid": guid, "wav": _repo_rel(cfg, wav), "text": text, "context": "", "speaker": r.get("speaker", ""),
            "engine": r.get("engine", ""), "voice_source": r.get("voice_source", ""), "dur": round(dur, 2),
            "cps": round(len(spoken) / dur, 1) if dur else 0, "emotion": "", "instruct": "",
            "ref_path": ref, "ref": Path(ref).stem if ref else "",
            "real": real.get(guid.removeprefix("lexall-").replace("_", " "), []),
            "old": _repo_rel(cfg, old) if old.is_file() else None, "heard": a.get("heard", ""), "wer": a.get("wer"),
            "flags": auto_flags(dur, len(spoken), r.get("flags", [])) + a.get("flags", []),
        })
    return out


def _stamp(d: Path, run: str) -> tuple:
    names = ("index.json",) if run == EXPORT else ("manifest.jsonl", "asr.jsonl", "real.json")
    return tuple((d / n).stat().st_mtime_ns if (d / n).exists() else 0 for n in names)


def clips(cfg: Config, run: str = EXPORT) -> list[dict]:
    d = _run_dir(cfg, run)
    key, stamp = (str(cfg.root), run), _stamp(d, run)
    hit = _CLIPS.get(key)
    if hit and hit[0] == stamp:
        return hit[1]
    out = _export_clips(cfg, d) if run == EXPORT else _run_clips(cfg, d)
    _CLIPS[key] = (stamp, out)
    return out


def runs(cfg: Config) -> list[dict]:
    exp = read_json(cfg.render / "export/index.json", {})
    out = [{"id": EXPORT, "label": "Merged export", "clips": len(exp)}]
    for m in sorted(glob.glob(str(cfg.render / "*/manifest.jsonl"))):
        n = sum(1 for ln in open(m, encoding="utf-8") if ln.strip())
        out.append({"id": Path(m).parent.name, "label": Path(m).parent.name, "clips": n})
    return out


def facets(cfg: Config, run: str = EXPORT) -> dict:
    cs = clips(cfg, run)
    uniq = lambda vals: sorted({v for v in vals if v})
    return {"speakers": uniq(c["speaker"] for c in cs), "refs": uniq(c["ref"] for c in cs),
            "engines": uniq(c["engine"] for c in cs), "flags": uniq(f for c in cs for f in c["flags"])}


def _verdicts_path(cfg: Config, run: str) -> Path:
    return cfg.render / "audit" / ("verdicts.json" if run == EXPORT else f"verdicts_{run}.json")


def get_verdicts(cfg: Config, run: str = EXPORT) -> dict:
    return read_json(_verdicts_path(cfg, run), {})


def _sort_key(sort: str):
    if sort == "slowest":
        return lambda c: (c["cps"], c["guid"])
    if sort == "fastest":
        return lambda c: (-c["cps"], c["guid"])
    if sort == "longest":
        return lambda c: (-c["dur"], c["guid"])
    if sort == "shortest":
        return lambda c: (c["dur"], c["guid"])
    return lambda c: (-len(c["flags"]), -abs(c["cps"] - TYPICAL_CPS), c["guid"])      # suspicious


def page(cfg: Config, run: str = EXPORT, *, speaker=None, ref=None, engine=None, flag=None, verdict=None, q=None,
         sort="suspicious", seed=0, offset=0, limit=DEFAULT_LIMIT) -> dict:
    if sort not in SORTS:
        raise ApiError(400, f"sort must be one of {SORTS}")
    cs, judged = clips(cfg, run), get_verdicts(cfg, run)
    good = sum(1 for c in cs if judged.get(c["guid"], {}).get("verdict") == "good")
    bad = sum(1 for c in cs if judged.get(c["guid"], {}).get("verdict") == "bad")
    want = (q or "").lower()

    def keep(c: dict) -> bool:
        v = judged.get(c["guid"], {}).get("verdict")
        if speaker and c["speaker"] != speaker or ref and c["ref"] != ref or engine and c["engine"] != engine:
            return False
        if want and want not in c["text"].lower():
            return False
        if flag and not (c["flags"] if flag == "any flag" else not c["flags"] if flag == "no flag" else flag in c["flags"]):
            return False
        return not verdict or (v is None if verdict == "unjudged" else v == verdict)

    shown = [c for c in cs if keep(c)]
    if sort == "random":
        shown.sort(key=lambda c: c["guid"])
        random.Random(int(seed)).shuffle(shown)
    else:
        shown.sort(key=_sort_key(sort))
    limit, offset = max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))
    items = [{**c, "verdict": judged.get(c["guid"])} for c in shown[offset:offset + limit]]
    return {"total": len(shown), "offset": offset, "limit": limit, "items": items,
            "stats": {"good": good, "bad": bad, "unjudged": len(cs) - good - bad}}


def set_verdict(cfg: Config, run: str, body: dict) -> dict:
    guid, verdict = body.get("guid"), body.get("verdict")
    tags, note = body.get("tags", []), body.get("note", "")
    if not isinstance(guid, str) or not guid:
        raise ApiError(400, "guid is required")
    if verdict is not None and verdict not in VERDICTS:
        raise ApiError(400, f"verdict must be one of {VERDICTS} or null")
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags) or not isinstance(note, str):
        raise ApiError(400, "tags must be a list of strings and note a string")
    if guid not in {c["guid"] for c in clips(cfg, run)}:
        raise ApiError(404, f"no clip {guid!r} in {run}")
    path = _verdicts_path(cfg, run)
    with STATE_LOCK:
        v = read_json(path, {})
        if verdict is None:
            v.pop(guid, None)
        else:
            v[guid] = {"verdict": verdict, "tags": tags, "note": note}
        write_json_atomic(path, v)
    return {}


def compressed(path: Path, fx: str) -> bytes:
    """The wav with the consonant-burst compressor applied (the old page's A/B). Needs numpy and scipy."""
    root = Path(__file__).resolve().parents[4] / "tools/render_corpus"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import numpy as np
        from deburst import PRESETS, deburst
    except ImportError as e:
        raise ApiError(501, f"the compressor needs numpy and scipy: {e}")
    if fx not in PRESETS:
        raise ApiError(400, f"fx must be one of {sorted(PRESETS)}")
    key = (str(path), fx, path.stat().st_mtime_ns)
    if key in _FX:
        return _FX[key]
    with wave.open(str(path)) as w:
        ch, sr = w.getnchannels(), w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    y = np.clip(deburst(x, sr, **PRESETS[fx]), -1, 1)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype("<i2").tobytes())
    if len(_FX) >= FX_CACHE_MAX:
        _FX.clear()
    _FX[key] = out.getvalue()
    return _FX[key]
