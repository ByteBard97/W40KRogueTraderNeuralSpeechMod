"""Render one job from a recipe: prepare the text, render each piece with quality control, join, check the result.

A job carries `recipe` (the Render Lab's recipe: model options, pronunciation, punctuation, split, joins). Each piece is rendered by
`raw(text, ref_wav, instruct, cfg, timesteps, normalize, seed)`; a piece whose speech is overdriven (low crest factor) is
re-rendered up the ladder in `qc` (new seed, then a lower cfg) and the best take of the piece is kept. The pieces are then trimmed,
loudness-matched, softened and joined exactly as the lab does, and the joined take is measured again. Nothing here needs torch.

Retried too: a piece with a run of clipped samples (the model's output hit its ceiling).

Job field `recipe.qc` (all optional): {"min_crest_db": 11, "attempts": 4, "seed_retries": 1, "cfg_step": 0.5, "min_cfg": 1.5, "min_seconds": 1.0}.
"""
from __future__ import annotations

import hashlib

import numpy as np

import recipe_audio as A
import recipe_text as T
from jobs import take_problem

QC_DEFAULT = {"min_crest_db": A.CREST_BAD_DB, "attempts": 4, "seed_retries": 1, "cfg_step": 0.5, "min_cfg": 1.5, "min_seconds": 1.0}
SEED_RANGE = 2 ** 31
ATTEMPT_SEED_STRIDE = 1000


def stable_seed(guid: str, salt: str = "") -> int:
    return int(hashlib.md5(f"{guid}|{salt}".encode()).hexdigest()[:8], 16) % SEED_RANGE


def piece_cfg(base: float, attempt: int, qc: dict) -> float:
    """The cfg for an attempt: unchanged for the first attempts (they only change the seed), then stepped down, never below min_cfg."""
    steps = max(0, attempt - int(qc["seed_retries"]))
    return max(float(qc["min_cfg"]), base - steps * float(qc["cfg_step"])) if steps else base


def render_piece(raw, text: str, ref_wav: str, instruct, recipe: dict, seed: int, qc: dict):
    """(audio, sr, info) for the best of up to qc["attempts"] takes of one piece."""
    best = None
    for attempt in range(int(qc["attempts"])):
        cfg = piece_cfg(float(recipe["cfg"]), attempt, qc)
        wav, sr = raw(text, ref_wav, instruct, cfg, int(recipe["timesteps"]), bool(recipe.get("normalize")), seed + attempt * ATTEMPT_SEED_STRIDE)
        m = A.metrics(wav, sr)
        short = m["seconds"] < float(qc["min_seconds"])               # a very short piece has no stable crest factor
        ok = short or (m["crest_db"] is not None and m["crest_db"] >= float(qc["min_crest_db"]) and m["clip_runs"] == 0)
        score = 99.0 if short else (m["crest_db"] or 0.0) - 5.0 * m["clip_runs"]       # a clipped take loses to a clean one of similar crest
        if best is None or score > best[0]:
            best = (score, wav, sr, {"attempts": attempt + 1, "cfg": cfg, "crest_db": m["crest_db"], "ok": ok, "model_peak": float(np.abs(wav).max())})
        if ok:
            break
    best[3]["attempts"] = attempt + 1                      # how many takes were made, not which one was kept
    return best[1], best[2], best[3]


def render_recipe(raw, job: dict, ref_wav: str):
    """(manifest row, joined wav, sample rate). Raises whatever `raw` raises; the worker turns that into a failed row."""
    recipe = {**job["recipe"]}
    qc = {**QC_DEFAULT, **(recipe.get("qc") or {})}
    prep = T.prepare(job["text"], recipe)
    instruct = T.instruct_for(recipe, job.get("annotation"))
    base = stable_seed(job["guid"], str(recipe.get("seed", "")))
    chunks, gaps, info, sr = [], [], [], 24000
    for i, piece in enumerate(prep["pieces"]):
        wav, sr, d = render_piece(raw, piece["text"], ref_wav, instruct, recipe, base + i, qc)
        chunks.append(wav)
        gaps.append(piece["gap_ms"] or 0)
        info.append(d)
    if recipe.get("trim_silence"):
        chunks = [A.trim_silence(c, sr) for c in chunks]
    if recipe.get("level_match"):
        chunks = A.match_levels(chunks, sr)
    soft = float(recipe.get("onset_soften_db") or 0)
    if soft < 0:
        chunks = [c if i == 0 else A.soften_onset(c, sr, soft, int(recipe.get("onset_soften_ms", 150))) for i, c in enumerate(chunks)]
    model_peak = max(d["model_peak"] for d in info)
    audio = A.limit_peak(A.join(chunks, gaps, sr), recipe.get("peak_limit_db"))
    m = A.metrics(audio, sr)
    flags = [m["flag"]] if m["flag"] else []
    if any(not d["ok"] for d in info):
        flags.append("piece_overdriven")
    problem = take_problem(job["text"], len(audio) / sr)
    if problem:
        flags.append(problem)
    row = {"guid": job["guid"], "speaker": job["speaker"], "engine": "voxcpm2", "text": job["text"], "src_text": job["src_text"],
           "voice_source": job["voice_source"], "status": "ok", "seconds": round(len(audio) / sr, 2), "flags": flags,
           "recipe": recipe.get("name", "recipe"), "pieces": len(chunks), "crest_db": m["crest_db"], "model_peak": round(model_peak, 3),
           "attempts": [d["attempts"] for d in info], "cfg_used": [d["cfg"] for d in info]}
    return row, audio, sr


def render_recipe_job(raw, job: dict, ref_wav: str):
    """render_recipe, but an engine error becomes a failed row (the queue retries it), like render.render_take."""
    import traceback
    try:
        return render_recipe(raw, job, ref_wav)
    except Exception as e:
        traceback.print_exc()
        return {"guid": job["guid"], "speaker": job["speaker"], "engine": "voxcpm2", "text": job["text"], "src_text": job["src_text"],
                "voice_source": job["voice_source"], "status": "failed", "error": str(e)[:200]}, None, None
