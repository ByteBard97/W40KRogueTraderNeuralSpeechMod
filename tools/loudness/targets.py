"""Per-speaker loudness targets from the real game voice-over (data/loudness/stats.jsonl, set "real").

  python3 tools/loudness/targets.py          # rebuild data/loudness/targets.json
Loudness is integrated LUFS; a speaker with no real VO (and the narrator) gets the overall real-VO median.
"""
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
STATS = ROOT / "data/loudness/stats.jsonl"
TARGETS = ROOT / "data/loudness/targets.json"
MIN_CLIPS = 20      # fewer real clips than this and a speaker's median is not trusted
DEFAULT_KEY = "_default"


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def build() -> dict:
    by: dict[str, list[float]] = {}
    for line in STATS.read_text().splitlines():
        r = json.loads(line)
        if r["set"] == "real" and r["I"] > -70:
            by.setdefault(r["group"], []).append(r["I"])
    allv = [v for vs in by.values() for v in vs]
    out = {DEFAULT_KEY: round(float(np.median(allv)), 1)}
    for k, vs in by.items():
        if len(vs) >= MIN_CLIPS and not k.startswith("_"):
            out[norm(k)] = round(float(np.median(vs)), 1)
    TARGETS.write_text(json.dumps(out, indent=1, sort_keys=True))
    return out


def load() -> dict:
    return json.loads(TARGETS.read_text()) if TARGETS.exists() else build()


def target_for(speaker: str, targets: dict | None = None) -> float:
    t = targets or load()
    if (speaker or "").lower() == "narrator":
        return t[DEFAULT_KEY]
    return t.get(norm(speaker), t[DEFAULT_KEY])


if __name__ == "__main__":
    print(json.dumps(build(), indent=1))
