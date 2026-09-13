#!/usr/bin/env python3
"""Builds a per-speaker "good emotion" vocabulary from Ultravox cross-mode agreement in
audio_llm_labels.json (see speaker_vocab.py for the gate itself and why confidence isn't
used). Writes:

  data/voices/emotion_banks/speaker_vocab.json   - machine-readable, consumed by
                                                    tools/annotate/schema.py's per-speaker
                                                    EMOTIONS override
  data/voices/emotion_banks/speaker_vocab_report.md - human-readable audit: word counts,
                                                    example clips per word, comparison
                                                    against the legacy 12-word enum and
                                                    against curation.json ground truth

Usage:
  python3 build_speaker_vocab.py [--speaker Abelard] [--threshold 3] [--top-k 2]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from speaker_vocab import build_agreement_counts, select_vocab
from vocab import EMOTION_ORDER, load_vocab

ROOT = Path(__file__).resolve().parent.parent.parent
VOICES = ROOT / "data/voices"
LABELS_PATH = VOICES / "emotion_banks/audio_llm_labels.json"
CATALOG_PATH = VOICES / "catalog.json"
CURATION_PATH = VOICES / "emotion_banks/curation.json"
CUSTOM_EMOTIONS_PATH = VOICES / "emotion_banks/custom_emotions.json"
OUT_JSON = VOICES / "emotion_banks/speaker_vocab.json"
OUT_REPORT = VOICES / "emotion_banks/speaker_vocab_report.md"

EXAMPLES_PER_WORD = 5  # capped for report readability; full list still goes in the JSON


def _latest_entry(mode_dict: dict) -> dict | None:
    """mode_dict: prompt_hash -> entry. Normally has exactly one key; if the prompt
    template changed and produced a second hash, prefer the most recent labeling."""
    if not mode_dict:
        return None
    return max(mode_dict.values(), key=lambda e: e.get("timestamp", ""))


def speaker_labels_for(labels: dict, catalog: dict, speaker: str) -> dict:
    """event -> {"audio": entry_or_None, "audio+text": entry_or_None}, Ultravox only,
    restricted to clips belonging to `speaker` and successfully parsed."""
    out = {}
    for event, backends in labels.items():
        if catalog.get(event, {}).get("speaker") != speaker:
            continue
        ultravox = backends.get("ultravox", {})
        audio = _latest_entry(ultravox.get("audio", {}))
        audio_text = _latest_entry(ultravox.get("audio+text", {}))
        if audio and not audio.get("parse_ok"):
            audio = None
        if audio_text and not audio_text.get("parse_ok"):
            audio_text = None
        if audio or audio_text:
            out[event] = {"audio": audio, "audio+text": audio_text}
    return out


def build_report(speaker: str, vocab_words: list[str], counts: Counter,
                  examples: dict[str, list[str]], threshold: int, top_k: int,
                  n_clips: int, human_words: set[str]) -> str:
    lines = [f"# Speaker vocabulary: {speaker}", "",
              f"Ultravox-agreement gate: word must appear in the top-{top_k} of both audio-only "
              f"and audio+text passes for the same clip, at least {threshold} times. "
              f"{n_clips} clips considered.", "",
              f"**Result: {len(vocab_words)} words.**", ""]
    if len(vocab_words) < 8:
        lines.append("Fewer than 8 words - narrower than the legacy 12-word enum. Consider "
                      "widening (lower `--threshold`, or union with curation.json ground truth "
                      "words) before wiring into annotate.py.")
        lines.append("")
    lines.append("| word | count | in legacy 12-word enum | example clips |")
    lines.append("|---|---|---|---|")
    for w in vocab_words:
        legacy = "yes" if w in EMOTION_ORDER else ""
        ex = ", ".join(examples[w][:EXAMPLES_PER_WORD])
        lines.append(f"| {w} | {counts[w]} | {legacy} | {ex} |")
    missing_human = sorted(human_words - set(vocab_words))
    if missing_human:
        lines += ["", f"**Human ground-truth words not covered by this vocabulary "
                       f"({len(missing_human)}):** " + ", ".join(missing_human)]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default=None, help="restrict to one speaker (default: all speakers present in audio_llm_labels.json)")
    ap.add_argument("--threshold", type=int, default=3, help="min cross-mode-agreement count to admit a word (default 3)")
    ap.add_argument("--top-k", type=int, default=2, help="how many ranked picks per mode count toward agreement (default 2)")
    args = ap.parse_args()

    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    curation = json.loads(CURATION_PATH.read_text(encoding="utf-8")) if CURATION_PATH.exists() else {}
    vocab = load_vocab(CUSTOM_EMOTIONS_PATH)
    valid_words = set(vocab["all_words"])

    speakers = [args.speaker] if args.speaker else sorted({catalog[e]["speaker"] for e in labels if e in catalog})

    out_data = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else {}
    report_sections = []

    for speaker in speakers:
        sp_labels = speaker_labels_for(labels, catalog, speaker)
        if not sp_labels:
            print(f"skip {speaker}: no Ultravox labels found")
            continue
        counts, examples = build_agreement_counts(sp_labels, valid_words, top_k=args.top_k)
        vocab_words = select_vocab(counts, args.threshold)
        human_words = {rec["emotion"] for rec in curation.get(speaker, {}).values() if rec.get("emotion")}

        out_data[speaker] = {
            "words": vocab_words,
            "threshold": args.threshold,
            "top_k": args.top_k,
            "n_clips_considered": len(sp_labels),
            "counts": dict(counts),
            "example_events": examples,
        }
        report_sections.append(build_report(speaker, vocab_words, counts, examples,
                                             args.threshold, args.top_k, len(sp_labels), human_words))
        print(f"{speaker}: {len(vocab_words)} words from {len(sp_labels)} clips -> {vocab_words}")

    OUT_JSON.write_text(json.dumps(out_data, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_REPORT.write_text("\n---\n\n".join(report_sections), encoding="utf-8")
    print(f"wrote {OUT_JSON} and {OUT_REPORT}")


if __name__ == "__main__":
    main()
