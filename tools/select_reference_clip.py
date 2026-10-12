#!/usr/bin/env python3
"""Pick the zero-shot voice-cloning reference clip for an unvoiced line, from a
speaker's real, ear-verified voiced clips (curation.json). Exact emotion match
preferred; when none exists, falls back to the nearest emotion by PAD (Pleasure/
Arousal/Dominance) distance (data/voices/emotion_banks/emotion_pad.json) and picks a
clip labeled with that nearest emotion instead - "no clip sounds exactly 'wistful',
but 'sad' is the closest real recorded emotion we have, so use a sad clip."

Usage (as a library):
    from select_reference_clip import ReferenceLibrary
    lib = ReferenceLibrary("Abelard")
    ref = lib.find("mournful")
    # ref: {"event", "wav", "text", "emotion", "distance", "exact_match": bool}

Usage (CLI, for inspection):
    python3 tools/select_reference_clip.py --speaker Abelard --emotion wistful
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATION_PATH = ROOT / "data/voices/emotion_banks/curation.json"
CATALOG_PATH = ROOT / "data/voices/catalog.json"
PAD_PATH = ROOT / "data/voices/emotion_banks/emotion_pad.json"
VOICES_DIR = ROOT / "data/voices"


class ReferenceLibrary:
    def __init__(self, speaker: str):
        self.speaker = speaker
        self.pad = json.loads(PAD_PATH.read_text(encoding="utf-8"))["words"]
        curation = json.loads(CURATION_PATH.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

        self.clips_by_emotion: dict[str, list[dict]] = {}
        for event, rec in curation.get(speaker, {}).items():
            emotion = rec.get("emotion")
            if not emotion:
                continue
            c = catalog.get(event)
            if not c or not c.get("texts"):
                continue
            self.clips_by_emotion.setdefault(emotion, []).append({
                "event": event,
                "wav": str(VOICES_DIR / c["wav"]),
                "text": c["texts"][0]["text"],
                "emotion": emotion,
                "duration": c.get("duration", 0),
                "decision": rec.get("decision"),
            })
        if not self.clips_by_emotion:
            raise SystemExit(f"no ear-verified emotion-labeled clips found for {speaker!r} "
                              f"in {CURATION_PATH}")

    def all_clips(self) -> list[dict]:
        return [c for clips in self.clips_by_emotion.values() for c in clips]

    def by_event(self, event: str) -> dict | None:
        return next((c for c in self.all_clips() if c["event"] == event), None)

    def _best_of(self, clips: list[dict]) -> dict:
        """Prefer human-accepted clips, then longer ones (more robust zero-shot prompt,
        matching prompts.json's own >=5.5s preference elsewhere in this project)."""
        accepted = [c for c in clips if c["decision"] == "accept"]
        pool = accepted or clips
        return max(pool, key=lambda c: c["duration"])

    def find(self, target_emotion: str) -> dict:
        if target_emotion in self.clips_by_emotion:
            best = self._best_of(self.clips_by_emotion[target_emotion])
            return {**best, "distance": 0.0, "exact_match": True,
                    "matched_emotion": target_emotion}

        if target_emotion not in self.pad:
            raise SystemExit(f"{target_emotion!r} has no PAD coordinates in {PAD_PATH} - "
                              f"add it there first")
        tv, ta, td = (self.pad[target_emotion][k] for k in ("valence", "arousal", "dominance"))

        best_emotion, best_dist = None, float("inf")
        for candidate_emotion in self.clips_by_emotion:
            if candidate_emotion not in self.pad:
                continue  # a curated word with no PAD entry yet - skip rather than guess
            cv, ca, cd = (self.pad[candidate_emotion][k] for k in ("valence", "arousal", "dominance"))
            dist = ((cv - tv) ** 2 + (ca - ta) ** 2 + (cd - td) ** 2) ** 0.5
            if dist < best_dist:
                best_emotion, best_dist = candidate_emotion, dist

        if best_emotion is None:
            raise SystemExit(f"no clips for {self.speaker!r} have a PAD-scored emotion at all")
        best = self._best_of(self.clips_by_emotion[best_emotion])
        return {**best, "distance": round(best_dist, 3), "exact_match": False,
                "matched_emotion": best_emotion}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="Abelard")
    ap.add_argument("--emotion", required=True)
    args = ap.parse_args()
    lib = ReferenceLibrary(args.speaker)
    ref = lib.find(args.emotion)
    print(json.dumps(ref, indent=2))


if __name__ == "__main__":
    main()
