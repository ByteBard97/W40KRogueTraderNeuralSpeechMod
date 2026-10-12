"""Compare what a TTS take was supposed to say with what Whisper heard, and flag the kind of damage that matters:
spelled-out letters, dropped endings, inserted babble, general garbling. Pure text logic, no model needed."""
from __future__ import annotations

import difflib
import re

WARN_WER, BAD_WER = 0.12, 0.25
SPELLED_RUN = 3        # this many single letters in a row = the engine spelled something out
HALLUC_RUN = 4         # this many heard words with nothing to match = babble or a runaway
TRUNC_WORDS = 3        # this many missing words at the very end = cut off


def words(text: str) -> list[str]:
    t = text.lower().replace("—", " ").replace("–", " ").replace("-", " ").replace("’", "'")
    return re.findall(r"[a-z0-9']+", t)


def _lex_tokens(terms) -> set[str]:
    return {w for t in terms for w in words(t)}


def compare(ref: str, hyp: str, lex_terms=()) -> dict:
    """ref/hyp are plain text. Words of lexicon terms and tokens with digits in `ref` are exempt from the error count:
    Whisper has no reason to spell invented 40K words or numbers the way the script does."""
    r, h = words(ref), words(hyp)
    exempt = _lex_tokens(lex_terms)
    ignorable = [w in exempt or any(c.isdigit() for c in w) for w in r]
    sm = difflib.SequenceMatcher(None, r, h, autojunk=False)
    errors = inserted_run = trunc = 0
    counted_ref = sum(not x for x in ignorable)
    for tag, a0, a1, b0, b1 in sm.get_opcodes():
        if tag == "equal":
            continue
        ref_bad = sum(not ignorable[i] for i in range(a0, a1))
        if tag == "insert":
            errors += b1 - b0
            inserted_run = max(inserted_run, b1 - b0)
        else:
            errors += max(ref_bad, (b1 - b0) if ref_bad else 0)
            if tag == "replace" and ref_bad:
                inserted_run = max(inserted_run, (b1 - b0) - (a1 - a0))
            if a1 == len(r) and ref_bad >= TRUNC_WORDS and b1 - b0 < ref_bad:
                trunc = ref_bad
    wer = errors / counted_ref if counted_ref else 0.0
    run = best = 0
    for w in h:
        run = run + 1 if len(w) == 1 and w not in ("a",) else 0
        best = max(best, run)
    flags = []
    if wer >= BAD_WER:
        flags.append("asr_bad")
    elif wer >= WARN_WER:
        flags.append("asr_warn")
    if best >= SPELLED_RUN:
        flags.append("asr_spelled")
    if trunc:
        flags.append("asr_truncated")
    if inserted_run >= HALLUC_RUN:
        flags.append("asr_extra_words")
    return {"wer": round(wer, 3), "flags": flags}
