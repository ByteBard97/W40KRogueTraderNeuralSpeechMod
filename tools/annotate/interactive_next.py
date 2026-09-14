#!/usr/bin/env python3
"""Show the next unlabeled Abelard conversation (or chunk) for interactive labeling.
Prints the whole conversation - or a chunk of it, for the minority too long to read in
one pass - with every other speaker's lines for context and Abelard's remaining
unvoiced target lines marked. Read-only; writing labels is interactive_submit.py's job.

Usage: interactive_next.py [--cache-dir DIR] [--chunk-size N] [--chunk-overlap N]
                            [conv_guid [chunk_index]]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from context_window import (  # noqa: E402
    abelard_targets, canonical_chunk, chunk_ranges, dialogue_lines,
    target_indices, unlabeled_targets, validate_chunk_params,
)
from schema import NONVERBALS, PACES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE_DIR = ROOT / "data/annotations/cache_claude_abelard"
DEFAULT_VOICED_CACHE_DIR = ROOT / "data/annotations/cache_claude_abelard_voiced"
CONVERSATIONS_PATH = ROOT / "data/conversations.enGB.json"
BIOS_PATH = ROOT / "data/character_bios.json"
VOCAB_PATH = ROOT / "data/voices/emotion_banks/speaker_vocab.json"
# Derived from schema.py, never redefined by hand - see the plan's Global Constraints.
PACES_LINE = "Paces: " + ", ".join(PACES)
NONVERBAL_LINE = "Nonverbal (optional): " + ", ".join(NONVERBALS)


def scan_already_labeled_keys(cache_dir: Path, exclude_path: Path | None = None) -> set[str]:
    """Every text_key with a label anywhere in cache_dir, across every conversation's
    cache file - the global dedup set (see context_window.unlabeled_targets).
    `exclude_path` (the file this call is about to revisit, if any) is skipped, so
    revisiting a conversation to check or correct it doesn't see its own prior output
    as already-labeled-elsewhere - see interactive_submit.py's function of the same
    name, which needed this for the same reason."""
    keys = set()
    for f in cache_dir.glob("*.json"):
        if exclude_path is not None and f.resolve() == exclude_path.resolve():
            continue
        for rec in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            keys.add(rec["guid"])
    return keys


def speaker_label(line: dict) -> str:
    sp = line.get("speaker") or {}
    return sp.get("name") or sp.get("kind") or "unknown"


def resolve_chunk_params(cache_dir: Path, conv_guid: str,
                          cli_chunk_size: int, cli_overlap: int) -> tuple[int, int]:
    """Same logic as interactive_submit.py's helper of the same name - duplicated
    rather than cross-imported, see this file's docstring."""
    existing = sorted(cache_dir.glob(f"{conv_guid}__chunk*.json"))
    if not existing:
        return cli_chunk_size, cli_overlap
    recorded = json.loads(existing[0].read_text(encoding="utf-8"))
    return recorded["chunk_size"], recorded["chunk_overlap"]


def render(conv: dict, chunk_index: int, chunk_size: int, overlap: int,
           already_labeled: set[str], bios: dict, vocab: list[str], voiced: bool = False) -> str:
    dialogue = dialogue_lines(conv)
    all_targets = abelard_targets(conv, voiced=voiced)
    idx_by_key = dict(zip((t["text_key"] for t in all_targets),
                          target_indices(dialogue, all_targets)))
    ranges = chunk_ranges(dialogue, list(idx_by_key.values()), chunk_size, overlap)
    start, end = ranges[chunk_index]
    canonical_by_key = {key: canonical_chunk(idx, ranges) for key, idx in idx_by_key.items()}

    header = [
        f"Conversation: {conv.get('name')} ({conv['guid']}) — "
        f"chunk {chunk_index + 1}/{len(ranges)} ({end - start} lines"
        + (f", overlap {overlap})" if len(ranges) > 1 else ")"),
        f"Abelard — {bios.get('Abelard', '')}",
        "Vocabulary: " + ", ".join(vocab),
        PACES_LINE + " | " + NONVERBAL_LINE,
        "",
    ]

    body = []
    canonical_here = []
    elsewhere_here = []
    seen_target_keys: set[str] = set()
    for i in range(start, end):
        line = dialogue[i]
        key = line["text_key"]
        text = line["text"]
        # `key in seen_target_keys` guards a real corpus shape (LucidIdira_dialogue has
        # the same text_key for Abelard twice in one conversation - abelard_targets()
        # already dedupes it to one required label, but dialogue_lines() intentionally
        # keeps both physical lines for display). Without this guard both physical
        # occurrences would independently render as a target marker for the same key,
        # implying two labels are needed when only one is - the second occurrence just
        # renders as plain dialogue instead.
        if key not in idx_by_key or key in seen_target_keys:
            body.append(f"[{speaker_label(line)}] {text}")
            continue
        seen_target_keys.add(key)
        is_canonical_here = canonical_by_key[key] == chunk_index and key not in already_labeled
        if is_canonical_here:
            canonical_here.append(key)
            body.append(f">>> [{key}] Abelard: {text}")
        else:
            elsewhere_here.append(key)
            where = "already labeled" if key in already_labeled else \
                f"labeled in chunk {canonical_by_key[key] + 1}"
            body.append(f"··· [{key}] Abelard ({where}): {text}")

    footer = [
        "",
        f"Targets in this chunk: {', '.join(canonical_here) if canonical_here else '(none)'}",
    ]
    if elsewhere_here:
        footer.append(f"(already labeled elsewhere, shown for context only: "
                       f"{', '.join(elsewhere_here)})")
    chunk_flag = f" --chunk {chunk_index}" if chunk_index else ""
    voiced_flag = " --voiced" if voiced else ""
    footer.append(f"Submit with: interactive_submit.py{voiced_flag} {conv['guid']}{chunk_flag} <json-file>")
    return "\n".join(header + body + footer)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("conv_guid", nargs="?", default=None)
    ap.add_argument("chunk_index", nargs="?", type=int, default=0)
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--chunk-size", type=int, default=50)
    ap.add_argument("--chunk-overlap", type=int, default=10)
    ap.add_argument("--voiced", action="store_true",
                    help="label Abelard's ~84 already-voiced lines (real game audio) "
                         "instead of the unvoiced corpus - a ground-truth pass to "
                         "calibrate his emotional range before labeling unvoiced text")
    args = ap.parse_args()

    validate_chunk_params(args.chunk_size, args.chunk_overlap)
    default_dir = DEFAULT_VOICED_CACHE_DIR if args.voiced else DEFAULT_CACHE_DIR
    cache_dir = Path(args.cache_dir) if args.cache_dir else default_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    convs = json.loads(CONVERSATIONS_PATH.read_text(encoding="utf-8"))
    bios = json.loads(BIOS_PATH.read_text(encoding="utf-8")) if BIOS_PATH.exists() else {}
    vocab = json.loads(VOCAB_PATH.read_text(encoding="utf-8"))["Abelard"]["words"]
    already_labeled = scan_already_labeled_keys(cache_dir)

    if args.conv_guid:
        conv = next((c for c in convs if c.get("guid") == args.conv_guid), None)
        if conv is None:
            print(f"no conversation with guid {args.conv_guid!r}", file=sys.stderr)
            sys.exit(1)
        chunk_size, overlap = resolve_chunk_params(cache_dir, args.conv_guid,
                                                    args.chunk_size, args.chunk_overlap)
        all_targets = abelard_targets(conv, voiced=args.voiced)
        dialogue = dialogue_lines(conv)
        idxs = target_indices(dialogue, all_targets)
        ranges = chunk_ranges(dialogue, idxs, chunk_size, overlap)
        if args.chunk_index < 0 or args.chunk_index >= len(ranges):
            # Python's negative-index semantics (ranges[-1] silently returning the last
            # chunk) would otherwise make a negative chunk_index look like it worked.
            print(f"chunk {args.chunk_index} does not exist for this conversation "
                  f"(it has {len(ranges)} chunk(s), valid range 0-{len(ranges) - 1})",
                  file=sys.stderr)
            sys.exit(1)
        chunked = len(ranges) > 1
        out_path = (cache_dir / f"{args.conv_guid}__chunk{args.chunk_index}.json" if chunked
                    else cache_dir / f"{args.conv_guid}.json")
        already_labeled_here = scan_already_labeled_keys(cache_dir, exclude_path=out_path)
        print(render(conv, args.chunk_index, chunk_size, overlap, already_labeled_here, bios, vocab,
                      voiced=args.voiced))
        return

    for conv in convs:
        all_targets = abelard_targets(conv, voiced=args.voiced)
        remaining = unlabeled_targets(all_targets, already_labeled)
        if not remaining:
            continue
        chunk_size, overlap = resolve_chunk_params(cache_dir, conv["guid"],
                                                    args.chunk_size, args.chunk_overlap)
        dialogue = dialogue_lines(conv)
        idx_by_key = dict(zip((t["text_key"] for t in all_targets),
                              target_indices(dialogue, all_targets)))
        ranges = chunk_ranges(dialogue, list(idx_by_key.values()), chunk_size, overlap)
        remaining_keys = {t["text_key"] for t in remaining}
        canonical_indices_for_remaining = {
            canonical_chunk(idx, ranges) for key, idx in idx_by_key.items() if key in remaining_keys
        }
        chunk_index = min(canonical_indices_for_remaining)
        print(render(conv, chunk_index, chunk_size, overlap, already_labeled, bios, vocab,
                      voiced=args.voiced))
        return

    print("Nothing left to label - every Abelard target has a cache entry.")


if __name__ == "__main__":
    main()
