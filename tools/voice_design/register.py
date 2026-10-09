#!/usr/bin/env python3
"""Register picked designed voices in the shared prompt bank (data/voices/prompts/prompts.json).

plan.py looks speakers up there by exact conversation name, so after registering, re-running
tools/render_corpus/plan.py moves those NPC's lines from voice_source "fallback" to "prompt_bank".
Picks live in data/voice_design/audit.json ({name: {"pick": "c3.wav", ...}}). Never deletes anything;
copying the clip to data/voices/prompts/designed/<slug>.wav keeps the approved voice stable even if
the candidate folder is regenerated.
"""
from __future__ import annotations

import json
import shutil
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VOICE_DESIGN = ROOT / "data/voice_design"
PROMPTS = ROOT / "data/voices/prompts/prompts.json"


def _duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return round(w.getnframes() / w.getframerate(), 2)


def register(audit: dict, manifest: dict, prompts: dict, vd_root: Path = VOICE_DESIGN,
             voices_root: Path = ROOT / "data/voices") -> list[str]:
    """Mutate `prompts` for every pick; returns the names registered."""
    done = []
    for name, a in audit.items():
        cand, m = a.get("pick"), manifest.get(name)
        if not cand or not m:
            continue
        src = vd_root / "clips" / m["slug"] / cand
        if not src.is_file():
            continue
        dst = voices_root / "prompts/designed" / f"{m['slug']}.wav"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        prompts[name] = [{"rank": 1, "event": f"designed_{m['slug']}", "wav": f"prompts/designed/{m['slug']}.wav",
                          "text": m["text"], "duration": _duration(dst),
                          "source": f"Qwen3-TTS VoiceDesign: {m['description']}"}]
        done.append(name)
    return done


def main() -> None:
    audit = json.loads((VOICE_DESIGN / "audit.json").read_text(encoding="utf-8"))
    manifest = json.loads((VOICE_DESIGN / "design_manifest.json").read_text(encoding="utf-8"))
    prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
    done = register(audit, manifest, prompts)
    PROMPTS.write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"registered {len(done)}: {done}")


if __name__ == "__main__":
    sys.exit(main())
