#!/usr/bin/env python3
"""Plot a histogram of emotion label counts from an interactive-annotation cache dir,
with the x-axis grouped by data/voices/emotion_banks/custom_emotions.json's energy
tiers (Low energy -> Low-mid -> Mid -> Mid-high -> High -> Register modifiers ->
Custom) instead of alphabetical or arbitrary order, so visually adjacent bars are
emotionally similar.

Usage: python3 tools/plot_emotion_histogram.py [--cache-dir DIR] [--out PATH] [--title TEXT]

Default --cache-dir is data/annotations/cache_claude_abelard_voiced (the ground-truth
pass over Abelard's voiced lines); point it elsewhere (e.g.
data/annotations/cache_claude_abelard, the unvoiced harness's output) to plot any other
interactive-annotation cache directory in the same cache-file format.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = ROOT / "data/annotations/cache_claude_abelard_voiced"
CUSTOM_EMOTIONS_PATH = ROOT / "data/voices/emotion_banks/custom_emotions.json"


def count_emotions(cache_dir: Path) -> Counter:
    """Every emotion value across every *.json cache file's "lines" list."""
    counts: Counter = Counter()
    for f in sorted(cache_dir.glob("*.json")):
        for rec in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            counts[rec["emotion"]] += 1
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
    ap.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    ap.add_argument("--out", default=None,
                     help="output image path (default: <cache-dir>_histogram.png)")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir)
    counts = count_emotions(cache_dir)
    if not counts:
        print(f"no labels found in {cache_dir}", flush=True)
        return

    tiers = load_tiers()
    ordered = ordered_words(counts, tiers)
    out_path = Path(args.out) if args.out else cache_dir.parent / f"{cache_dir.name}_histogram.png"
    title = args.title or f"Emotion distribution: {cache_dir.name} ({sum(counts.values())} lines)"
    plot(counts, ordered, title, out_path)

    print(f"{sum(counts.values())} labeled lines, {len(counts)} distinct emotions")
    for word, tier in ordered:
        print(f"  [{tier}] {word}: {counts[word]}")
    print(f"-> {out_path}")


if __name__ == "__main__":
    main()
