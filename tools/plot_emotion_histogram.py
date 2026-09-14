#!/usr/bin/env python3
"""Plot a histogram of emotion label counts, with the x-axis grouped by
data/voices/emotion_banks/custom_emotions.json's energy tiers (Low energy -> Low-mid ->
Mid -> Mid-high -> High -> Register modifiers -> Custom) instead of alphabetical or
arbitrary order, so visually adjacent bars are emotionally similar.

Two data sources, pick one:

  --curation-speaker NAME   Real, ear-verified human labels from curation.json - the
                             correct source for a voiced character's true emotional
                             range, since a human actually listened to the recording.
                             This is what curate.html itself is built on.

  --cache-dir DIR           An interactive-annotation cache dir (interactive_next.py/
                             interactive_submit.py's output format) - text-only, agent-
                             assigned labels. Use this for the UNVOICED corpus, where no
                             audio exists to listen to and a context-aware read is the
                             only signal available. Do NOT use this for a voiced
                             character's calibration profile - a text-only guess is
                             strictly weaker evidence than a human who actually listened,
                             and mixing the two silently understates how much real
                             ground truth already exists (this mistake was made once
                             already for Abelard: a 53-line text-only pass was reported
                             as "his real range" when 136 of his 307 real voiced lines
                             already had a human ear-verified label in curation.json).

Usage:
  python3 tools/plot_emotion_histogram.py --curation-speaker Abelard [--out PATH] [--title TEXT]
  python3 tools/plot_emotion_histogram.py --cache-dir data/annotations/cache_claude_abelard
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURATION_PATH = ROOT / "data/voices/emotion_banks/curation.json"
CUSTOM_EMOTIONS_PATH = ROOT / "data/voices/emotion_banks/custom_emotions.json"


def count_emotions_from_cache(cache_dir: Path) -> Counter:
    """Every emotion value across every *.json cache file's "lines" list - text-only,
    agent-assigned. See this module's docstring for when this is (and isn't) the right
    source."""
    counts: Counter = Counter()
    for f in sorted(cache_dir.glob("*.json")):
        for rec in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            counts[rec["emotion"]] += 1
    return counts


def count_emotions_from_curation(speaker: str) -> Counter:
    """Every human-assigned emotion in curation.json for one speaker - real, ear-
    verified ground truth (a human listened to the actual recording and picked this).
    The correct source for a voiced character's calibration profile."""
    if not CURATION_PATH.exists():
        return Counter()
    curation = json.loads(CURATION_PATH.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for rec in curation.get(speaker, {}).values():
        emotion = rec.get("emotion")
        if emotion:
            counts[emotion] += 1
    return counts


def load_tiers() -> list[dict]:
    if not CUSTOM_EMOTIONS_PATH.exists():
        return []
    return json.loads(CUSTOM_EMOTIONS_PATH.read_text(encoding="utf-8")).get("tiers", [])


def ordered_words(counts: Counter, tiers: list[dict]) -> list[tuple[str, str]]:
    """(word, tier_name) pairs in x-axis order: each tier's words that actually appear
    in `counts`, in the tier's own listed order, tiers in their given sequence; any
    counted word absent from every tier (e.g. the original 12-word enum's "whisper",
    "commanding") goes last under "Unclassified" - still shown, never silently dropped."""
    placed = []
    seen = set()
    for tier in tiers:
        for word in tier["words"]:
            if word in counts and word not in seen:
                placed.append((word, tier["tier"]))
                seen.add(word)
    for word in counts:
        if word not in seen:
            placed.append((word, "Unclassified"))
            seen.add(word)
    return placed


def plot(counts: Counter, ordered: list[tuple[str, str]], title: str, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    words = [w for w, _ in ordered]
    values = [counts[w] for w in words]
    tier_names = [t for _, t in ordered]
    tier_colors = {}
    palette = plt.get_cmap("tab10").colors
    colors = []
    for t in tier_names:
        if t not in tier_colors:
            tier_colors[t] = palette[len(tier_colors) % len(palette)]
        colors.append(tier_colors[t])

    fig, ax = plt.subplots(figsize=(max(8, len(words) * 0.5), 5))
    ax.bar(range(len(words)), values, color=colors)
    ax.set_xticks(range(len(words)))
    ax.set_xticklabels(words, rotation=45, ha="right")
    ax.set_ylabel("count")
    ax.set_title(title)

    # One legend entry per tier actually shown, in first-seen order.
    handles = [plt.Rectangle((0, 0), 1, 1, color=tier_colors[t]) for t in dict.fromkeys(tier_names)]
    ax.legend(handles, list(dict.fromkeys(tier_names)), loc="upper right", fontsize="small")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--curation-speaker", default=None,
                     help="plot real human-verified labels for this speaker from "
                          "curation.json (recommended for any voiced character)")
    ap.add_argument("--cache-dir", default=None,
                     help="plot an interactive-annotation cache dir instead (text-only "
                          "labels - use for the unvoiced corpus, not a voiced one)")
    ap.add_argument("--out", default=None, help="output image path")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    if bool(args.curation_speaker) == bool(args.cache_dir):
        raise SystemExit("pass exactly one of --curation-speaker or --cache-dir")

    if args.curation_speaker:
        counts = count_emotions_from_curation(args.curation_speaker)
        source_label = f"curation.json:{args.curation_speaker}"
        default_out = ROOT / f"data/voices/emotion_banks/{args.curation_speaker}_curated_histogram.png"
        default_title = (f"{args.curation_speaker}: real emotional range "
                          f"(n={sum(counts.values())}, human ear-verified)")
        source_note = "no labels found" if not counts else None
    else:
        cache_dir = Path(args.cache_dir)
        counts = count_emotions_from_cache(cache_dir)
        source_label = str(cache_dir)
        default_out = cache_dir.parent / f"{cache_dir.name}_histogram.png"
        default_title = f"Emotion distribution: {cache_dir.name} ({sum(counts.values())} lines)"
        source_note = f"no labels found in {cache_dir}" if not counts else None

    if not counts:
        print(source_note, flush=True)
        return

    tiers = load_tiers()
    ordered = ordered_words(counts, tiers)
    out_path = Path(args.out) if args.out else default_out
    title = args.title or default_title
    plot(counts, ordered, title, out_path)

    print(f"source: {source_label}")
    print(f"{sum(counts.values())} labeled lines, {len(counts)} distinct emotions")
    for word, tier in ordered:
        print(f"  [{tier}] {word}: {counts[word]}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
