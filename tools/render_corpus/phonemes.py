"""Lexicon words as CMUDict phonemes in braces, for VoxCPM2.

VoxCPM2 spells out the capitalised respellings the other engines read as words ("SIR-vih-tur" -> S-I-R), and
lowercase respellings are unreliable too. Braced phonemes are what its docs specify for pronunciation control.
A lexicon entry may carry "arpabet": "S ER1 V IH0 T ER0" to override the phonemes derived from its IPA, or
"voxcpm2": "plain" to hand the model the ordinary word, or "voxcpm2": "<any other text>" to substitute that text.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/TtsSidecar"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lexicon  # noqa: E402
from ipa_to_arpabet import ipa_to_arpabet  # noqa: E402


def phonemize(text: str) -> str:
    entries, pattern = lexicon._load()

    def sub(m):
        e = entries[m.group(1).lower()]
        mode = e.get("voxcpm2")
        if mode == "plain":
            out = m.group(1)
        elif mode:
            out = mode   # literal text for this word, e.g. a lowercase respelling that works better than phonemes
        elif e.get("arpabet"):
            out = "{" + e["arpabet"] + "}"
        else:
            out = ipa_to_arpabet(e["ipa"])
        return out + " " if m.group(0).endswith("-") else out
    return pattern.sub(sub, text)
