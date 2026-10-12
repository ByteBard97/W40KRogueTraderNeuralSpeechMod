"""Pure logic for the corpus renderer: bucketing, engine choice, take sanity check, worker selection.

Kept free of torch/numpy so the unit tests and the planner run anywhere.
"""
from __future__ import annotations

import hashlib
import re

BUCKETS = 100
# VoxCPM2's own docs call inputs under ~1 s of speech unstable (see
# docs/research/voxcpm2-in-character-consistency-findings.md); short lines go to Qwen3-TTS.
SHORT_LINE_CHARS = 50
# Seconds of audio per character of text for legitimate output tops out near 0.1-0.2 (qwen3_tts.py).
MIN_SEC_PER_CHAR = 0.03
MAX_SEC_PER_CHAR = 0.35
MIN_RUNAWAY_SECONDS = 8.0


def bucket_of(guid: str) -> int:
    return int(hashlib.md5(guid.encode()).hexdigest(), 16) % BUCKETS


def parse_buckets(spec: str) -> range:
    """'0-69' -> range(0, 70); '30' -> range(30, 31). Inclusive on both ends."""
    lo, _, hi = spec.partition("-")
    lo_i, hi_i = int(lo), int(hi or lo)
    if not (0 <= lo_i <= hi_i < BUCKETS):
        raise ValueError(f"bad bucket spec {spec!r}")
    return range(lo_i, hi_i + 1)


def choose_engine(spoken_text: str) -> str:
    return "qwen3_tts" if len(spoken_text) < SHORT_LINE_CHARS else "voxcpm2"


def take_problem(spoken_text: str, seconds: float) -> str | None:
    """Cheap bad-take detector: runaways, truncations and silence show up as an implausible rate."""
    n = max(1, len(spoken_text))
    rate = seconds / n
    if seconds < 0.4:
        return "too_short"
    if rate > MAX_SEC_PER_CHAR and seconds > MIN_RUNAWAY_SECONDS:  # 1.2 s for "Ah!" is fine
        return "too_long"
    if rate < MIN_SEC_PER_CHAR and n > 20:
        return "too_fast"
    return None


def select_jobs(jobs: list[dict], engine: str, buckets: range, done: set[str]) -> list[dict]:
    """Jobs this worker should render, highest priority first (stable by guid)."""
    mine = [j for j in jobs
            if j["engine"] == engine and j["bucket"] in buckets and j["guid"] not in done]
    mine.sort(key=lambda j: (j["priority"], j["guid"]))
    return mine


_BINARY_RUN = re.compile(r"(?<![0-9])[01]{16,}(?![0-9])")


def decode_binary(text: str) -> str:
    """Spoken form of long binary strings. TTS engines try to read every digit and run away (a 160-digit
    machine-cant line produced 198 s of audio), so decode 8-bit ASCII when it reads as text, else say 'binary code'."""
    def sub(m: re.Match) -> str:
        b = m.group(0)
        if len(b) % 8 == 0:
            s = "".join(chr(int(b[i:i + 8], 2)) for i in range(0, len(b), 8))
            if s.isprintable() and re.search(r"[A-Za-z]", s):
                return s
        return "binary code"
    return _BINARY_RUN.sub(sub, text)
