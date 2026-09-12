"""Combined emotion vocabulary: the original 12-emotion enum plus the tiered custom
vocabulary in data/voices/emotion_banks/custom_emotions.json."""
from __future__ import annotations

import json
from pathlib import Path

EMOTION_ORDER = ["angry", "commanding", "fear", "surprised", "pleading", "sad", "whisper",
                  "sarcastic", "dramatic", "happy", "amused", "neutral"]

ENERGY_LADDER = ["Low energy", "Low-mid energy", "Mid energy", "Mid-high energy", "High energy"]


def load_vocab(custom_emotions_path: Path) -> dict:
    tiers = [{"tier": "Original", "words": list(EMOTION_ORDER)}]
    if custom_emotions_path.exists():
        tiers += json.loads(custom_emotions_path.read_text(encoding="utf-8")).get("tiers", [])
    word_to_tier = {w: t["tier"] for t in tiers for w in t["words"]}
    all_words = [w for t in tiers for w in t["words"]]
    return {"tiers": tiers, "word_to_tier": word_to_tier, "all_words": all_words}
