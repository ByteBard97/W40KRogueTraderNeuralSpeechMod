from __future__ import annotations

import shutil
import threading
import time

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic
from .speakers import find_speaker, studio_dir

OPTION_DEFAULTS = {"cfg": 2.0, "timesteps": 10, "seed": "", "use_instruct": False, "retry_badcase": False,
                   "normalize": False, "continuation": False}
ORIGINS = ("real", "designed", "supplied")
_LAST_ID = [0]
_ID_LOCK = threading.Lock()


def new_take_id() -> str:
    """Millisecond timestamp id, forced strictly increasing within the process."""
    with _ID_LOCK:
        n = max(int(time.time() * 1000), _LAST_ID[0] + 1)
        _LAST_ID[0] = n
    return f"t{n}"


def get_profile(cfg: Config, slug: str) -> dict | None:
    return read_json(studio_dir(cfg, slug) / "profile.json", None)


def save_profile(cfg: Config, slug: str, body: dict) -> dict:
    sp = find_speaker(cfg, slug)
    src = body.get("source") or {}
    if src.get("origin") not in ORIGINS:
        raise ApiError(400, f"source.origin must be one of {ORIGINS}")
    if cfg.under_data(src.get("wav", "")) is None:
        raise ApiError(400, f"source.wav is not a file under data/: {src.get('wav')!r}")
    opts = {k: (body.get("options") or {}).get(k, v) for k, v in OPTION_DEFAULTS.items()}
    prof = {"name": sp["name"], "slug": slug, "kind": "speaker",
            "source": {"wav": src["wav"], "text": src.get("text", ""), "origin": src["origin"]},
            "options": opts, "fx": list(body.get("fx") or []), "test_lines": list(body.get("test_lines") or []),
            "notes": body.get("notes", ""), "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
    with STATE_LOCK:
        write_json_atomic(studio_dir(cfg, slug) / "profile.json", prof)
    return prof


def set_active(cfg: Config, slug: str) -> dict:
    find_speaker(cfg, slug)
    src = studio_dir(cfg, slug) / "profile.json"
    if not src.is_file():
        raise ApiError(404, "save a profile first")
    shutil.copyfile(src, studio_dir(cfg, slug) / "active.json")
    return {"active": f"data/studio/{slug}/active.json"}


def read_takes(cfg: Config, slug: str) -> dict:
    return read_json(studio_dir(cfg, slug) / "takes.json", {})


def add_take(cfg: Config, slug: str, take: dict) -> dict:
    with STATE_LOCK:
        takes = read_takes(cfg, slug)      # raises 500 on a corrupt file before anything is written
        takes[take["id"]] = take
        write_json_atomic(studio_dir(cfg, slug) / "takes.json", takes)
    return take


def update_take(cfg: Config, slug: str, take_id: str, **fields) -> dict:
    with STATE_LOCK:
        takes = read_takes(cfg, slug)
        if take_id not in takes:
            raise ApiError(404, f"no take '{take_id}'")
        takes[take_id].update(fields)
        write_json_atomic(studio_dir(cfg, slug) / "takes.json", takes)
        return takes[take_id]
