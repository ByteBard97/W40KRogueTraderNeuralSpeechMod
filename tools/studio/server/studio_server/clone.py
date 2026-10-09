from __future__ import annotations

import shutil

from .config import Config
from .errors import ApiError
from .speakers import find_speaker, studio_dir
from .store import add_take, new_take_id, read_takes, update_take

MAX_RATING = 5


def _check_options(o: dict) -> None:
    seed = str(o.get("seed", "")).strip()
    if seed and not seed.isdigit():
        raise ApiError(400, f"seed must be blank or a whole number, got {seed!r}")
    for key in ("cfg", "timesteps"):
        v = o.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            raise ApiError(400, f"{key} must be a positive number, got {v!r}")


def generate(cfg: Config, model, slug: str, body: dict) -> dict:
    find_speaker(cfg, slug)
    ref = body.get("reference") or {}
    if cfg.under_data(ref.get("wav", "")) is None:
        raise ApiError(400, f"reference is not a file under data/: {ref.get('wav')!r}")
    o = body["options"]
    _check_options(o)
    read_takes(cfg, slug)       # a corrupt takes.json must stop us before a generation is spent on it
    req = {"text": body["text"], "reference_wav": ref["wav"], "seed": o.get("seed", ""), "cfg": o["cfg"],
           "timesteps": o["timesteps"], "retry_badcase": o["retry_badcase"], "normalize": o["normalize"]}
    if o.get("use_instruct") and body.get("instruct"):
        req["instruct"] = body["instruct"]
    if o.get("continuation"):
        req["prompt_text"] = ref.get("text", "")
    r = model.call("/generate", req)
    take_id = new_take_id()
    # The backend's live_tmp is scratch space. Keep the studio's own copy so a take never loses its audio.
    raw = studio_dir(cfg, slug) / "raw" / f"{take_id}.wav"
    raw.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cfg.voice_design / r["file"], raw)
    take = {"id": take_id, "raw": f"data/studio/{slug}/raw/{take_id}.wav", "text": body["text"],
            "guid": body.get("guid"), "reference": ref["wav"], "options": o, "instruct": req.get("instruct"),
            "seed": r["seed"], "seconds": r["seconds"], "audio_s": r.get("audio_s"), "rating": 0, "note": "",
            "fx": None}
    return add_take(cfg, slug, take)


def rate_take(cfg: Config, slug: str, take_id: str, body: dict) -> dict:
    fields = {}
    if "rating" in body:
        if not isinstance(body["rating"], int) or not 0 <= body["rating"] <= MAX_RATING:
            raise ApiError(400, f"rating must be an integer 0 to {MAX_RATING}")
        fields["rating"] = body["rating"]
    if "note" in body:
        fields["note"] = str(body["note"])
    return update_take(cfg, slug, take_id, **fields)
