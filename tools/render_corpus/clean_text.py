"""Make game text safe to hand to a TTS engine: resolve the game's template markup and strip symbols that
the engines read aloud or run away on."""
from __future__ import annotations

import re

PLAYER_ADDRESS = "Lord Captain"   # the player's name is never spoken: the audio is baked and players name their own character
# {rt_mf|him|her} takes the first (male) form, as the default Rogue Trader is male


def clean_for_tts(text: str) -> str:
    t = re.sub(r"\{rt_mf\|([^|}]*)\|[^}]*\}", r"\1", text)          # {rt_mf|his|her} -> his
    t = t.replace("{rt_name}", PLAYER_ADDRESS)
    t = re.sub(r"(?<=[A-Za-z])'(?=Lord Captain)", " ", t)           # Domin'{name} arrives as "Domin'Lord Captain"
    t = re.sub(r"(?<=[A-Za-z0-9])(?=Lord Captain)|(?<=Lord Captain)(?=[A-Za-z0-9])", " ", t)   # the filled-in title never glues onto its neighbours
    t = re.sub(r"\{[^{}|]*\|([^|{}]*)(?:\|[^{}]*)?\}", r"\1", t)     # any other {tag|first|...} -> first
    t = re.sub(r"//([^/\n]+?)(?://(?=[^\s.,;:!?])[^/\n]+?)+//(?=[\s.,;:!?]|$)", r"\1", t)   # //a//b//c// alternatives -> a
    t = re.sub(r"(?<![:/])/{2,}", " ", t)                            # ///log markers
    t = re.sub(r"(?<=\w\)) / (?=\d)|(?<=\w) / (?=\d)", " divided by ", t)             # (Awareness / 10)
    t = re.sub(r"\b([A-Za-z]+)/([A-Za-z]+)\b", r"\1", t)             # he/she -> he
    t = re.sub(r"(?<=\w)/(?=\w)", " ", t)                            # LD-987/A14 -> LD-987 A14
    t = re.sub(r"\bUnit (?=your pet|the (?:raven|dog))", "", t)         # "Unit {petname}'s owner"
    t = t.replace("||", ", ")
    t = t.replace("~", "")
    t = re.sub(r"[\[\]<>*#@^`\\|=+_]", " ", t)                    # brackets and stray symbols, glitch tildes
    t = re.sub(r"\.{4,}", "...", t)
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


_CODE_BRACKET = re.compile(r"\[[^\]\n]*\d[^\]\n]*\]")


def is_terminal_log(raw: str) -> bool:
    """Text that is a computer-terminal readout (///-prefixed log lines, [Alg.123] codes). Read aloud by a narrator it
    just sounds bad, so narrator lines like this are not rendered. Call it on the text before clean_for_tts."""
    return "///" in raw or "||" in raw or len(_CODE_BRACKET.findall(raw)) >= 2
