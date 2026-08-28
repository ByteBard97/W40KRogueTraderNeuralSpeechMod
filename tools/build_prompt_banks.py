#!/usr/bin/env python3
"""Select reference ("prompt") clips per speaker for zero-shot voice cloning.

Reads data/voices/catalog.json + wavs, scores each clip on cheap signal heuristics,
and writes data/voices/prompts/<speaker>/ with the top clips plus prompts.json
(clip -> transcript, duration, scores). Zero-shot TTS models want 5-30 s of clean,
dry, mid-energy speech; the transcript comes from the localization text, so models
that take (audio, text) prompts (F5, Fish) get both.

Scoring favors: duration in range, high speech level without clipping, low noise floor
(quietest 10% of frames), single continuous utterance (few long pauses), and a
text length consistent with the audio duration (~12-20 chars/sec of speech).
"""
from __future__ import annotations

import argparse
import json
import re
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
VOICES = ROOT / "data/voices"


def load_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
        width = w.getsampwidth()
        ch = w.getnchannels()
    if width == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    elif width == 4:
        x = np.frombuffer(raw, dtype=np.float32)
    else:
        raise ValueError(f"unsupported sample width {width}")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def score_clip(x: np.ndarray, sr: int, text: str) -> dict:
    dur = len(x) / sr
    frame = int(0.03 * sr)
    if len(x) < frame * 10:
        return {"ok": False, "reason": "too short"}
    frames = x[: len(x) // frame * frame].reshape(-1, frame)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-12)
    speech_db = float(np.percentile(db, 90))
    noise_db = float(np.percentile(db, 10))
    peak = float(np.abs(x).max())
    active = db > (speech_db - 18)
    # longest pause in seconds
    pauses, run = [], 0
    for a in active:
        run = 0 if a else run + 1
        pauses.append(run)
    longest_pause = max(pauses) * 0.03 if pauses else 0.0
    speech_secs = float(active.sum()) * 0.03
    chars_per_sec = len(re.sub(r"\s+", " ", text)) / max(0.3, speech_secs) if text else 0.0

    s = 0.0
    s += max(0, 1 - abs(dur - 8) / 8)                      # prefer ~4-12 s
    s += min(1.0, (speech_db - (-30)) / 15)                # decent level
    s += min(1.0, max(0.0, (speech_db - noise_db - 25) / 25))  # clean floor
    s += 0 if peak > 0.99 else 0.5                          # not clipped
    s += 0.5 if longest_pause < 0.7 else 0.0                # continuous
    if text:
        s += 0.5 if 8 <= chars_per_sec <= 24 else 0.0       # audio matches text length
    return {"ok": True, "score": round(float(s), 3), "duration": round(dur, 2),
            "speech_db": round(speech_db, 1), "noise_db": round(noise_db, 1),
            "peak": round(peak, 3), "longest_pause": round(longest_pause, 2),
            "chars_per_sec": round(chars_per_sec, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--min-dur", type=float, default=3.0)
    ap.add_argument("--max-dur", type=float, default=15.0)
    ap.add_argument("--speakers", nargs="*", default=None)
    args = ap.parse_args()

    catalog = json.load(open(VOICES / "catalog.json", encoding="utf-8"))
    by_speaker: dict[str, list] = {}
    for event, c in catalog.items():
        if not (args.min_dur <= c["duration"] <= args.max_dur):
            continue
        text = c["texts"][0]["text"] if c.get("texts") else ""
        # skip lines that are mostly stage direction or contain little speech
        if not text or len(text) < 20:
            continue
        by_speaker.setdefault(c["speaker"], []).append((event, c, text))

    prompts = {}
    out_root = VOICES / "prompts"
    for speaker, clips in sorted(by_speaker.items()):
        if args.speakers and speaker not in args.speakers:
            continue
        if speaker.startswith("_") or len(clips) < 3:
            continue
        scored = []
        for event, c, text in clips:
            try:
                x, sr = load_wav(VOICES / c["wav"])
            except Exception:
                continue
            sc = score_clip(x, sr, text)
            if sc.get("ok"):
                scored.append((sc["score"], event, c, text, sc))
        scored.sort(key=lambda t: -t[0])
        chosen = scored[: args.top]
        sdir = out_root / re.sub(r"[^A-Za-z0-9_-]", "_", speaker)
        sdir.mkdir(parents=True, exist_ok=True)
        entries = []
        for rank, (score, event, c, text, sc) in enumerate(chosen, 1):
            dst = sdir / f"{rank:02d}_{Path(c['wav']).name}"
            dst.write_bytes((VOICES / c["wav"]).read_bytes())
            entries.append({"rank": rank, "event": event, "wav": str(dst.relative_to(VOICES)),
                            "text": text, **sc})
        prompts[speaker] = entries
        print(f"{speaker}: {len(clips)} candidates -> {len(entries)} prompts "
              f"(best score {entries[0]['score'] if entries else 0})")

    (out_root / "prompts.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
