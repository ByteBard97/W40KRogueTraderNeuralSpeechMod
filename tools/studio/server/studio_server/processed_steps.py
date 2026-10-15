"""The render pipeline's rule that processed voices clone with more steps (tools/render_corpus/processed.py), for the Render Lab's test takes."""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

from .config import Config

PIPELINE_MODULE = Path(__file__).resolve().parents[4] / "tools/render_corpus/processed.py"


@lru_cache(maxsize=1)
def _pipeline():
    spec = importlib.util.spec_from_file_location("rt_processed", PIPELINE_MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def steps_for(cfg: Config, speaker: str, steps: int) -> int:
    """`steps`, raised to the pipeline's processed count when the speaker's voice is processed (never lowered)."""
    p = _pipeline()
    return max(int(steps), p.PROCESSED_TIMESTEPS) if speaker in p.load(cfg.root) else int(steps)
