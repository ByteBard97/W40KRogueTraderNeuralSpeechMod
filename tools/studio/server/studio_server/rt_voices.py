"""Labels for the Rogue Trader voices that have game audio (data/voices/catalog.json), so the pipeline knows how each one sounds.

Same vocabulary as the BG3 labels (bg3_labels.SCHEMA) so the two kinds of voice can be compared, plus what only the game's own recordings
have: whether the voice is processed and with which effects, and how clean the clips are. The processing label feeds the render pipeline
(tools/render_corpus/processed.py: a processed speaker clones with more steps). Labels live in data/studio/rt_labels.json, one object per speaker name.
"""
from __future__ import annotations

from collections import defaultdict

from . import attribution, bg3_labels
from .config import Config
from .errors import ApiError
from .label_set import LabelSet

UNATTRIBUTED = "_unattributed"
SAMPLE_CLIPS = 3
SAMPLE_SECONDS = 7.0                 # clips nearest this length are the easiest to judge by ear
SAMPLE_MIN_S, SAMPLE_MAX_S = 3.0, 15.0
SHARED = ("gender", "age", "class", "processing", "pitch", "accent", "species", "texture", "energy", "pace")
EXTRA: list[dict] = [
    {"key": "effects", "label": "Effects", "kind": "multi", "required": False,
     "options": ["machine / vox-caster", "radio / comm", "echo / reverb", "pitch-shifted", "distorted / glitchy", "layered / choir"]},
    {"key": "clip_quality", "label": "Clip quality", "kind": "single", "required": False,
     "options": ["clean", "some noise or music", "effects or music bleed"]},
    {"key": "note", "label": "Note", "kind": "text", "options": [], "required": False},
]
SCHEMA: list[dict] = [dict(bg3_labels.BY_KEY[k]) for k in SHARED] + EXTRA
LABELS = LabelSet(SCHEMA, "rt_labels.json")


def speakers(cfg: Config) -> dict[str, dict]:
    """Speaker name -> clip count, seconds and a few sample clips, for every speaker with extracted game audio."""
    catalog = attribution.catalog(cfg)          # the extractor's catalog plus the speakers worked out for its unattributed clips
    by: dict[str, list[dict]] = defaultdict(list)
    for e in catalog.values():
        if e.get("speaker") and e["speaker"] != UNATTRIBUTED:
            by[e["speaker"]].append(e)
    out = {}
    for name, clips in by.items():
        fit = [e for e in clips if e.get("texts") and SAMPLE_MIN_S <= e.get("duration", 0) <= SAMPLE_MAX_S]
        fit.sort(key=lambda e: (abs(e["duration"] - SAMPLE_SECONDS), e["event"]))
        out[name] = {"clips": len(clips), "seconds": sum(e.get("duration", 0) for e in clips),
                     "refs": [{"wav": f"data/voices/{e['wav']}", "text": e["texts"][0]["text"], "seconds": e["duration"]} for e in fit[:SAMPLE_CLIPS]]}
    return out


def voices(cfg: Config) -> list[dict]:
    """The speakers in the shape the BG3 labelling page already draws, biggest first."""
    labels = LABELS.read_all(cfg)
    rows = [{"slug": name, "name": name, "lines": s["clips"], "minutes": round(s["seconds"] / 60, 1), "gender": "unclear", "f0": None, "non_human": False,
             "refs": s["refs"], "used_by": [], "quality": None, "aliases": [], "labels": labels.get(name, {}), "mine": labels.get(name, {}),
             "complete": LABELS.is_complete(labels.get(name, {}))} for name, s in speakers(cfg).items()]
    return sorted(rows, key=lambda r: (-r["lines"], r["name"]))


def page(cfg: Config) -> dict:
    vs = voices(cfg)
    return {"voices": vs, "schema": SCHEMA, "progress": LABELS.progress(cfg, vs)}


def set_label(cfg: Config, speaker: str, key: str, value) -> dict:
    if speaker not in speakers(cfg):
        raise ApiError(404, f"no game audio for {speaker!r}")
    return LABELS.set_label(cfg, speaker, key, value)
