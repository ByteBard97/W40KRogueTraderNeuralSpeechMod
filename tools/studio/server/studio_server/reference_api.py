"""Game-voice reference data for the pedalboard monitor: the FX Lab's reference.py, loaded by file path.

reference.py is shared with the FX Lab server (tools/fx_lab/server.py) and needs numpy, so it is imported lazily
and only when one of these endpoints is called.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

from .config import Config
from .errors import ApiError

REFERENCE_MODULE = Path(__file__).resolve().parents[4] / "tools/fx_lab/reference.py"


@lru_cache(maxsize=1)
def _reference():
    spec = importlib.util.spec_from_file_location("rt_fx_reference", REFERENCE_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def speakers(cfg: Config) -> list[dict]:
    """Speakers with game audio and their clip counts, most clips first."""
    return _reference().speakers(cfg.root)


def ltas(cfg: Config, speaker: str) -> dict:
    """Average spectrum and stereo stats of one speaker's clips; 400 without a name, 404 for an unknown speaker."""
    if not speaker:
        raise ApiError(400, "speaker is required")
    try:
        return _reference().ltas(cfg.root, speaker)
    except KeyError:
        raise ApiError(404, f"unknown speaker: {speaker}") from None
