"""Apply the 40K/RT pronunciation lexicon (data/lexicon/lexicon.json) to text before synthesis.

Two independent substitution modes, both loaded from the same entries:
  - respell(text): text-token engines (Chatterbox, Qwen3, Fish) - whole-word, case-insensitive
    replacement with the phonetic respelling. Longest terms are matched first so multi-word
    entries ("von valancius") take priority over their component words ("valancius").
  - ipa_ssml(text): phoneme-capable engines - wraps matches in SSML <phoneme> tags instead.
Both preserve the original capitalization pattern of the match is intentionally NOT attempted;
respellings carry their own stress capitalization (e.g. "om-NISS-ee-ah") which downstream
engines read as ordinary text.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEXICON_PATH = ROOT / "data/lexicon/lexicon.json"


@lru_cache(maxsize=1)
def _load() -> tuple[dict, re.Pattern]:
    entries = json.load(open(LEXICON_PATH, encoding="utf-8"))
    entries = {k: v for k, v in entries.items() if not k.startswith("_")}
    # longest terms first so multi-word entries win over their substrings
    terms = sorted(entries, key=len, reverse=True)
    # A term can appear as one half of a hyphenated compound (e.g. "vox-system",
    # "Chaos-branded") - 54 distinct cases across the corpus. `-` is a non-word char, so a plain
    # \bTERM\b already matches just the term there, but leaves the hyphen glued directly onto the
    # respelling with no separating space (e.g. "vox-system" -> "vokss-system" instead of "vokss
    # system"). Matching an optional trailing "-word" here lets the substitution turn that hyphen
    # into a space instead, without changing behavior for non-hyphenated matches.
    pattern = re.compile(r"\b(" + "|".join(re.escape(t) for t in terms) + r")(?:-(?=\w)|\b)",
                         re.IGNORECASE)
    return entries, pattern


def respell(text: str) -> str:
    entries, pattern = _load()
    def sub(m: re.Match) -> str:
        replacement = entries[m.group(1).lower()]["respell"]
        return replacement + " " if m.group(0).endswith("-") else replacement
    return pattern.sub(sub, text)


def ipa_ssml(text: str) -> str:
    entries, pattern = _load()
    def sub(m: re.Match) -> str:
        word = m.group(1)
        ipa = entries[word.lower()]["ipa"]
        tag = f'<phoneme alphabet="ipa" ph="{ipa}">{word}</phoneme>'
        return tag + " " if m.group(0).endswith("-") else tag
    return pattern.sub(sub, text)
