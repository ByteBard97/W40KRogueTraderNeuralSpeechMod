"""A set of owner labels over a list of voices: one schema, one JSON file in data/studio, one object per voice key.

The BG3 voices (bg3_labels.py) and the Rogue Trader voices that have game audio (rt_voices.py) each have a set. The schema is data: a list of
{"key", "label", "kind": "single" | "multi" | "text" | "rating", "options", "required"} with optional "allow_several" (a "single" label that may carry
more than one value, for a voice in an in-between spot). A voice is fully labelled when every required label is set, or when `done_when` says so.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .config import Config
from .errors import ApiError
from .jsonio import STATE_LOCK, read_json, write_json_atomic

MAX_TEXT = 500
BACKUP_EVERY_S = 1800


class LabelSet:
    def __init__(self, schema: list[dict], filename: str, done_when: Callable[[dict], bool] | None = None):
        self.schema = schema
        self.by_key = {d["key"]: d for d in schema}
        self.required = [d["key"] for d in schema if d["required"]]
        self.filename = filename
        self.done_when = done_when

    def path(self, cfg: Config) -> Path:
        return cfg.studio / self.filename

    def read_all(self, cfg: Config) -> dict[str, dict]:
        return read_json(self.path(cfg), {})

    def is_complete(self, mine: dict) -> bool:
        if self.done_when and self.done_when(mine):
            return True
        return all(mine.get(k) not in (None, "", []) for k in self.required)

    def check(self, key: str, value) -> object:
        d = self.by_key.get(key)
        if d is None:
            raise ApiError(400, f"unknown label {key!r}")
        if value in (None, "", []):
            return None
        if d["kind"] == "text":
            return str(value)[:MAX_TEXT]
        several = d["kind"] == "multi" or d.get("allow_several")
        if isinstance(value, list) and not several:
            raise ApiError(400, f"{key} takes one value")
        vals = value if isinstance(value, list) else [value]
        bad = [v for v in vals if v not in d["options"]]
        if bad:
            raise ApiError(400, f"{key} has no option {bad[0]!r}")
        ordered = [o for o in d["options"] if o in vals]
        return ordered if d["kind"] == "multi" or len(ordered) > 1 else ordered[0]      # one value stays a plain string

    def set_label(self, cfg: Config, slug: str, key: str, value) -> dict:
        """Set (or, with an empty value, clear) one label of one voice. Returns that voice's labels."""
        clean = self.check(key, value)
        with STATE_LOCK:
            labels = self.read_all(cfg)
            mine = labels.setdefault(slug, {})
            if clean is None:
                mine.pop(key, None)
            else:
                mine[key] = clean
            if not mine:
                labels.pop(slug, None)
            write_json_atomic(self.path(cfg), labels)
            self._rolling_backup(cfg)
        return labels.get(slug, {})

    def _rolling_backup(self, cfg: Config) -> None:
        """Hours of labelling are worth a copy: keep one at least every half hour while labels are being set."""
        stem = Path(self.filename).stem
        mine = list(self.path(cfg).parent.glob(f"{stem}.*.bak.json"))
        if not mine or time.time() - max(f.stat().st_mtime for f in mine) > BACKUP_EVERY_S:
            self.backup(cfg)

    def backup(self, cfg: Config) -> str | None:
        """Timestamped copy of the labels file."""
        p = self.path(cfg)
        if not p.is_file():
            return None
        dst = p.with_name(f"{Path(self.filename).stem}.{time.strftime('%Y%m%d-%H%M%S')}.bak.json")
        dst.write_bytes(p.read_bytes())
        return dst.name

    def progress(self, cfg: Config, voices: list[dict]) -> dict:
        labels = self.read_all(cfg)
        done = sum(1 for v in voices if self.is_complete(labels.get(v["slug"], {})))
        return {"total": len(voices), "complete": done, "started": sum(1 for v in voices if labels.get(v["slug"]))}
