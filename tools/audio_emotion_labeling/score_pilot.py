"""Pilot accuracy report: compares audio_llm_labels.json against the hand-labeled Abelard
ground truth in curation.json, per (backend, mode, prompt_hash)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from scoring import best_of_set_similarity, recall_at_k, tier_similarity
from vocab import load_vocab

ROOT = Path(__file__).resolve().parent.parent.parent
VOICES = ROOT / "data/voices"

_VARIANT_SUFFIX = re.compile(r" \[.*\]$")


def build_report(ground_truth: dict[str, str], labels: dict, word_to_tier: dict,
                  backend: str, mode: str, prompt_hash_value: str,
                  event_context: dict | None = None) -> dict:
    n_scored = 0
    top1_hits = 0
    recall_hits = {1: 0, 2: 0, 3: 0}
    similarities = []
    agree_confidences = []
    disagree_confidences = []
    disagreements = []
    notes_used = 0

    for event, human_word in ground_truth.items():
        entry = labels.get(event, {}).get(backend, {}).get(mode, {}).get(prompt_hash_value)
        if entry is None:
            continue
        n_scored += 1
        model_words = [l["word"] for l in entry["labels"]]
        top1 = model_words[0] if model_words else None
        top1_confidence = entry["labels"][0]["confidence"] if entry["labels"] else None

        if top1 == human_word:
            top1_hits += 1
            if top1_confidence is not None:
                agree_confidences.append(top1_confidence)
        else:
            disagreement = {"event": event, "human": human_word, "model": model_words,
                             "notes": entry.get("notes", "")}
            if event_context is not None:
                ctx = event_context.get(event, {})
                disagreement["transcript"] = ctx.get("transcript")
                disagreement["text_llm_emotion"] = ctx.get("text_llm_emotion")
            disagreements.append(disagreement)
            if top1_confidence is not None:
                disagree_confidences.append(top1_confidence)

        for k in (1, 2, 3):
            if recall_at_k(human_word, model_words, k):
                recall_hits[k] += 1

        similarities.append(best_of_set_similarity(human_word, model_words, word_to_tier))
        if entry.get("notes"):
            notes_used += 1

    def _mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    return {
        "backend": backend, "mode": mode, "n_scored": n_scored,
        "top1_exact": top1_hits / n_scored if n_scored else 0.0,
        "recall_at_1": recall_hits[1] / n_scored if n_scored else 0.0,
        "recall_at_2": recall_hits[2] / n_scored if n_scored else 0.0,
        "recall_at_3": recall_hits[3] / n_scored if n_scored else 0.0,
        "graded_similarity_mean": _mean(similarities) or 0.0,
        "mean_confidence_on_agreement": _mean(agree_confidences),
        "mean_confidence_on_disagreement": _mean(disagree_confidences),
        "notes_used_fraction": notes_used / n_scored if n_scored else 0.0,
        "disagreements": disagreements,
    }


def duplicate_base_lines(ground_truth: dict[str, str]) -> dict[str, list[str]]:
    """Base line name -> its Wwise state-variant sibling events, for base lines with more
    than one ground-truth event (see spec: 11 such pairs in the Abelard set)."""
    groups: dict[str, list[str]] = {}
    for event in ground_truth:
        base = _VARIANT_SUFFIX.sub("", event)
        groups.setdefault(base, []).append(event)
    return {base: events for base, events in groups.items() if len(events) > 1}


def _ground_truth() -> dict[str, str]:
    curation = json.loads((VOICES / "emotion_banks/curation.json").read_text(encoding="utf-8"))
    return {event: rec["emotion"] for speaker_clips in curation.values()
            for event, rec in speaker_clips.items() if rec.get("emotion")}


def _event_context() -> dict[str, dict]:
    """event -> {"transcript": str, "text_llm_emotion": str | None}, joining catalog.json's
    transcript to annotations.enGB.json's existing text-based LLM emotion guess via the
    shared localization GUID, at zero extra inference cost."""
    catalog = json.loads((VOICES / "catalog.json").read_text(encoding="utf-8"))
    annotations_path = ROOT / "data/annotations/annotations.enGB.json"
    annotations = json.loads(annotations_path.read_text(encoding="utf-8")) if annotations_path.exists() else {}
    context = {}
    for event, clip in catalog.items():
        texts = clip.get("texts") or []
        transcript = texts[0]["text"] if texts else None
        guid = texts[0]["guid"] if texts else None
        text_llm_emotion = annotations.get(guid, {}).get("emotion") if guid else None
        context[event] = {"transcript": transcript, "text_llm_emotion": text_llm_emotion}
    return context


def main() -> None:
    ground_truth = _ground_truth()
    labels = json.loads((VOICES / "emotion_banks/audio_llm_labels.json").read_text(encoding="utf-8"))
    vocab = load_vocab(VOICES / "emotion_banks/custom_emotions.json")
    event_context = _event_context()
    dupes = duplicate_base_lines(ground_truth)

    combos = {(b, m, ph) for evt in labels.values() for b, modes in evt.items()
              for m, phs in modes.items() for ph in phs}

    lines = ["# Pilot accuracy report\n",
             f"Duplicate base-line siblings among ground truth ({len(dupes)} base lines): "
             f"{dupes}\n"]
    for backend, mode, ph in sorted(combos):
        report = build_report(ground_truth, labels, vocab["word_to_tier"], backend, mode, ph,
                               event_context=event_context)
        lines.append(f"## {backend} / {mode} (prompt_hash={ph})\n")
        for key in ("n_scored", "top1_exact", "recall_at_1", "recall_at_2", "recall_at_3",
                    "graded_similarity_mean", "mean_confidence_on_agreement",
                    "mean_confidence_on_disagreement", "notes_used_fraction"):
            lines.append(f"- {key}: {report[key]}")
        lines.append(f"\n### Disagreements ({len(report['disagreements'])})\n")
        for d in report["disagreements"]:
            lines.append(f"- `{d['event']}`: human=`{d['human']}` model={d['model']} "
                          f"text_llm=`{d.get('text_llm_emotion')}` notes={d['notes']!r}\n"
                          f"  transcript: {d.get('transcript')!r}")
        lines.append("")

    out_path = VOICES / "emotion_banks/pilot_report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
