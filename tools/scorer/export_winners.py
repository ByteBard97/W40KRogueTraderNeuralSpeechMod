"""Export the winning take per line to a flat folder the mod/sidecar can consume.

Writes <out>/export/wav/<guid>.wav (copies) and <out>/export/index.json:
  {guid: {"wav": "wav/<guid>.wav", "text": ..., "emotion": ..., "voice_score": ..., "flags": [...]}}
Never deletes anything; stale files from earlier runs are overwritten only if the guid recurs.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def export_winners(out: Path, winners: dict[str, dict], root: Path = ROOT) -> int:
    ex = out / "export"
    (ex / "wav").mkdir(parents=True, exist_ok=True)
    index = {}
    for guid, w in winners.items():
        if w["status"] != "ok":
            continue
        src = root / w["wav"]
        if not src.is_file():
            continue
        dst = ex / "wav" / f"{guid}.wav"
        shutil.copyfile(src, dst)
        index[guid] = {"wav": f"wav/{guid}.wav", "text": w["text"], "emotion": w["emotion"],
                       "voice_score": w["voice_score"], "flags": w["flags"]}
    (ex / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(index)
