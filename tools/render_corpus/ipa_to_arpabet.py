"""Lexicon IPA (British) -> CMUDict-style phonemes, the form VoxCPM2 accepts in braces: "{S ER1 V IH0 T ER0}"."""
from __future__ import annotations

# longest first so digraphs and long vowels win
VOWELS = {"iː": "IY", "uː": "UW", "ɑː": "AA", "ɔː": "AO", "ɜː": "ER", "eɪ": "EY", "aɪ": "AY", "ɔɪ": "OY", "aʊ": "AW",
          "əʊ": "OW", "oʊ": "OW", "ɪ": "IH", "ɛ": "EH", "e": "EH", "æ": "AE", "ɒ": "AA", "ʊ": "UH", "ʌ": "AH", "ə": "AH",
          "ɑ": "AA", "ɔ": "AO", "i": "IY", "u": "UW", "a": "AA", "o": "OW"}
CONSONANTS = {"tʃ": "CH", "dʒ": "JH", "p": "P", "b": "B", "t": "T", "d": "D", "k": "K", "ɡ": "G", "g": "G", "f": "F", "v": "V",
              "θ": "TH", "ð": "DH", "s": "S", "z": "Z", "ʃ": "SH", "ʒ": "ZH", "h": "HH", "m": "M", "n": "N", "ŋ": "NG",
              "l": "L", "r": "R", "j": "Y", "w": "W"}
_TOKENS = sorted({**VOWELS, **CONSONANTS}, key=len, reverse=True)


def ipa_to_arpabet(ipa: str) -> str:
    """Multi-word entries give one brace group per word."""
    return " ".join(_word(w) for w in ipa.replace("-", " ").split())


def _word(ipa: str) -> str:
    out: list[str] = []
    stress = None
    i = 0
    while i < len(ipa):
        ch = ipa[i]
        if ch in "ˈˌ":
            stress = "1" if ch == "ˈ" else "2"
            i += 1
            continue
        tok = next((t for t in _TOKENS if ipa.startswith(t, i)), None)
        if tok is None:
            raise ValueError(f"unmapped IPA symbol {ch!r} in {ipa!r}")
        i += len(tok)
        if tok in VOWELS:
            out.append(VOWELS[tok] + (stress or "0"))
            stress = None
        else:
            out.append(CONSONANTS[tok])
    vowels = [i for i, p in enumerate(out) if p[-1].isdigit()]
    if len(vowels) == 1 and out[vowels[0]].endswith("0"):   # a one-syllable word is always stressed
        out[vowels[0]] = out[vowels[0]][:-1] + "1"
    return "{" + " ".join(out) + "}"
