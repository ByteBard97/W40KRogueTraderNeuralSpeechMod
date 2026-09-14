#!/usr/bin/env python3
"""Narrow down to the right emotion word by Pleasure(valence)/Arousal/Dominance instead
of scanning one flat energy-ordered list. Give a rough position on each axis (a
qualitative word or a -1.0..1.0 number) and get back the closest-matching vocabulary
words, nearest first - built because hand-labeling against a single "energy" axis made
it hard to find the right word when two candidates sit at similar energy but feel
completely different (e.g. "stern" vs "cautious": similar arousal, opposite dominance).

Usage:
  python3 tools/emotion_picker.py --valence negative --arousal calm --dominance low
  python3 tools/emotion_picker.py --valence -0.5 --arousal 0.2 --dominance -0.3 --top 5
  python3 tools/emotion_picker.py --valence negative --arousal calm --dominance low --speaker Abelard

--speaker restricts results to that character's speaker_vocab.json words, so suggestions
are always valid for actual submission via interactive_submit.py.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAD_PATH = ROOT / "data/voices/emotion_banks/emotion_pad.json"
SPEAKER_VOCAB_PATH = ROOT / "data/voices/emotion_banks/speaker_vocab.json"

# Qualitative anchors, so a rough guess doesn't require picking an exact float.
VALENCE_ANCHORS = {"very-negative": -0.8, "negative": -0.4, "neutral": 0.0,
                    "positive": 0.4, "very-positive": 0.8}
AROUSAL_ANCHORS = {"very-calm": -0.6, "calm": -0.3, "moderate": 0.0,
                    "activated": 0.3, "very-activated": 0.6}
DOMINANCE_ANCHORS = {"very-low": -0.6, "low": -0.3, "neutral": 0.0,
                      "high": 0.3, "very-high": 0.6}


def parse_axis(value: str, anchors: dict[str, float], axis_name: str) -> float:
    if value in anchors:
        return anchors[value]
    try:
        f = float(value)
    except ValueError:
        raise SystemExit(f"--{axis_name} must be a number in [-1, 1] or one of "
                          f"{sorted(anchors)}, got {value!r}")
    if not (-1.0 <= f <= 1.0):
        raise SystemExit(f"--{axis_name} {f} out of range [-1, 1]")
    return f


def load_pad_lexicon() -> dict[str, dict]:
    import json
    return json.loads(PAD_PATH.read_text(encoding="utf-8"))["words"]


def load_speaker_vocab(speaker: str) -> set[str] | None:
    import json
    if not SPEAKER_VOCAB_PATH.exists():
        return None
    vocab = json.loads(SPEAKER_VOCAB_PATH.read_text(encoding="utf-8"))
    entry = vocab.get(speaker)
    return set(entry["words"]) if entry else set()


def nearest_words(target: tuple[float, float, float], lexicon: dict[str, dict],
                   top: int, allowed: set[str] | None = None) -> list[tuple[str, float, dict]]:
    tv, ta, td = target
    scored = []
    for word, coords in lexicon.items():
        if allowed is not None and word not in allowed:
            continue
        dist = ((coords["valence"] - tv) ** 2 + (coords["arousal"] - ta) ** 2
                + (coords["dominance"] - td) ** 2) ** 0.5
        scored.append((word, dist, coords))
    scored.sort(key=lambda x: x[1])
    return scored[:top]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--valence", required=True,
                     help=f"one of {sorted(VALENCE_ANCHORS)} or a number in [-1, 1]")
    ap.add_argument("--arousal", required=True,
                     help=f"one of {sorted(AROUSAL_ANCHORS)} or a number in [-1, 1]")
    ap.add_argument("--dominance", required=True,
                     help=f"one of {sorted(DOMINANCE_ANCHORS)} or a number in [-1, 1]")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--speaker", default=None,
                     help="restrict results to this speaker's valid vocabulary "
                          "(data/voices/emotion_banks/speaker_vocab.json)")
    args = ap.parse_args()

    target = (
        parse_axis(args.valence, VALENCE_ANCHORS, "valence"),
        parse_axis(args.arousal, AROUSAL_ANCHORS, "arousal"),
        parse_axis(args.dominance, DOMINANCE_ANCHORS, "dominance"),
    )
    lexicon = load_pad_lexicon()

    allowed = None
    if args.speaker:
        allowed = load_speaker_vocab(args.speaker)
        if allowed is None:
            print(f"warning: no speaker_vocab.json entry for {args.speaker!r}, "
                  f"showing all words", flush=True)
            allowed = None
        elif not allowed:
            raise SystemExit(f"no vocabulary entry for speaker {args.speaker!r}")

    results = nearest_words(target, lexicon, args.top, allowed)
    if not results:
        print("no matching words (speaker vocabulary may not overlap the PAD lexicon)")
        return

    print(f"target: valence={target[0]:+.2f} arousal={target[1]:+.2f} dominance={target[2]:+.2f}")
    for word, dist, coords in results:
        print(f"  {word:16s} dist={dist:.2f}  "
              f"(v={coords['valence']:+.2f} a={coords['arousal']:+.2f} d={coords['dominance']:+.2f})")


if __name__ == "__main__":
    main()
