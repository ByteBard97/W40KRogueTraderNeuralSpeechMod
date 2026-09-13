#!/usr/bin/env python3
"""Validate and record Claude's interactive Abelard emotion labels for one conversation
(or one chunk of a long conversation). Writes into the same cache-file format
annotate.py's automated runs use, so --merge and diff_cache_vs_production.py consume it
unchanged.

Usage: interactive_submit.py [--cache-dir DIR] [--chunk N] [--chunk-size N]
                              [--chunk-overlap N] [--input PATH] <conv_guid> <json_file_or_->
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from context_window import (  # noqa: E402
    abelard_targets, canonical_chunk, chunk_ranges, dialogue_lines,
    target_indices, validate_chunk_params,
)
from schema import NONVERBALS, PACES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CACHE_DIR = ROOT / "data/annotations/cache_claude_abelard"
DEFAULT_CONVERSATIONS_PATH = ROOT / "data/conversations.enGB.json"
VOCAB_PATH = ROOT / "data/voices/emotion_banks/speaker_vocab.json"


class SubmitError(Exception):
    """A validation failure - nothing is written to disk when this is raised."""


def line_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def resolve_chunk_params(cache_dir: Path, conv_guid: str,
                          cli_chunk_size: int, cli_overlap: int) -> tuple[int, int]:
    """Reuse a conversation's already-recorded chunk_size/overlap if it has one, so
    retuning --chunk-size mid-corpus can't reshuffle boundaries for work already done."""
    existing = sorted(cache_dir.glob(f"{conv_guid}__chunk*.json"))
    if not existing:
        return cli_chunk_size, cli_overlap
    recorded = json.loads(existing[0].read_text(encoding="utf-8"))
    return recorded["chunk_size"], recorded["chunk_overlap"]


def load_abelard_vocab(vocab_path: Path = VOCAB_PATH) -> list[str]:
    vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
    return vocab["Abelard"]["words"]


def find_conversation(convs: list[dict], conv_guid: str) -> dict:
    for conv in convs:
        if conv.get("guid") == conv_guid:
            return conv
    raise SubmitError(f"no conversation with guid {conv_guid!r}")


def scan_already_labeled_keys(cache_dir: Path, exclude_path: Path | None = None) -> set[str]:
    """Every text_key with a label anywhere in cache_dir, across every conversation's
    cache file. `exclude_path` (the file this submission is about to overwrite, if any)
    is skipped, so resubmitting/correcting a chunk doesn't see its own prior output as
    an external conflict. Same logic as interactive_next.py's function of the same name
    - duplicated rather than cross-imported, see that file's docstring."""
    keys = set()
    for f in cache_dir.glob("*.json"):
        if exclude_path is not None and f.resolve() == exclude_path.resolve():
            continue
        for rec in json.loads(f.read_text(encoding="utf-8"))["lines"]:
            keys.add(rec["guid"])
    return keys


def required_targets_for_chunk(ranges: list[tuple[int, int]], targets: list[dict],
                                idxs: list[int], chunk: int,
                                already_labeled: set[str] = frozenset()) -> list[dict]:
    """The targets whose canonical chunk is exactly `chunk` and that don't already have
    a label elsewhere - what this submission must cover, no more, no less. A target
    merely rendered in this chunk via overlap, but canonical to a different chunk, is
    excluded here; so is a target already labeled via a different conversation (some
    targets share a text_key with another target, including across different
    conversations - see abelard_targets' docstring) - requiring it again here would
    make that conversation permanently unsubmittable."""
    if chunk < 0 or chunk >= len(ranges):
        raise SubmitError(f"chunk {chunk} does not exist for this conversation "
                           f"(it has {len(ranges)} chunk(s), valid range 0-{len(ranges) - 1})")
    return [t for t, idx in zip(targets, idxs)
            if canonical_chunk(idx, ranges) == chunk and t["text_key"] not in already_labeled]


def validate_submission(submitted: dict, required: list[dict], vocab: list[str]) -> list[dict]:
    """Validate `submitted` (text_key -> label dict) against `required` targets. Returns
    finished line records (with text_hash added), in `required`'s order. Raises
    SubmitError describing every problem with one target before giving up on it."""
    required_keys = {t["text_key"] for t in required}
    submitted_keys = set(submitted)
    missing = required_keys - submitted_keys
    unexpected = submitted_keys - required_keys
    errors = []
    if missing:
        errors.append(f"missing labels for: {', '.join(sorted(missing))}")
    if unexpected:
        errors.append(f"unexpected guids not in this chunk's required targets: "
                       f"{', '.join(sorted(unexpected))}")
    if errors:
        raise SubmitError("; ".join(errors))

    records = []
    for target in required:
        key = target["text_key"]
        rec = submitted[key]
        if not isinstance(rec, dict):
            raise SubmitError(f"{key}: label must be a JSON object, got {type(rec).__name__}")
        problems = []
        emotion = rec.get("emotion")
        if emotion not in vocab:
            problems.append(f"emotion {emotion!r} not in Abelard's vocabulary: {vocab}")
        pace = rec.get("pace")
        if pace not in PACES:
            problems.append(f"pace {pace!r} not one of {PACES}")
        nonverbal = rec.get("nonverbal", [])
        bad_nonverbal = [n for n in nonverbal if n not in NONVERBALS]
        if bad_nonverbal:
            problems.append(f"nonverbal entries not in {NONVERBALS}: {bad_nonverbal}")
        intensity = rec.get("intensity")
        if not isinstance(intensity, (int, float)) or not (0.0 <= intensity <= 1.0):
            problems.append(f"intensity {intensity!r} must be a number in [0, 1]")
        instruct = rec.get("instruct", "")
        if not instruct:
            problems.append("instruct must not be empty")
        elif len(instruct) > 300:
            problems.append(f"instruct is {len(instruct)} chars, must be <= 300")
        if problems:
            raise SubmitError(f"{key}: " + "; ".join(problems))
        records.append({
            "guid": key, "emotion": emotion, "intensity": float(intensity), "pace": pace,
            "nonverbal": nonverbal, "instruct": instruct, "text_hash": line_hash(target["text"]),
        })
    return records


def run(args: argparse.Namespace) -> None:
    validate_chunk_params(args.chunk_size, args.chunk_overlap)
    cache_dir = Path(args.cache_dir) if args.cache_dir else DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input) if args.input else DEFAULT_CONVERSATIONS_PATH
    convs = json.loads(input_path.read_text(encoding="utf-8"))
    conv = find_conversation(convs, args.conv_guid)

    targets = abelard_targets(conv)
    if not targets:
        raise SubmitError(f"conversation {args.conv_guid!r} has no Abelard targets")

    chunk_size, overlap = resolve_chunk_params(cache_dir, args.conv_guid,
                                                args.chunk_size, args.chunk_overlap)
    dialogue = dialogue_lines(conv)
    idxs = target_indices(dialogue, targets)
    ranges = chunk_ranges(dialogue, idxs, chunk_size, overlap)

    # Determined before validation, deliberately: scan_already_labeled_keys must exclude
    # this exact output file, or resubmitting/correcting the same chunk would see its
    # own prior labels as an external conflict and compute an empty required set.
    chunked = len(ranges) > 1
    out_path = (cache_dir / f"{args.conv_guid}__chunk{args.chunk}.json" if chunked
                else cache_dir / f"{args.conv_guid}.json")

    already_labeled = scan_already_labeled_keys(cache_dir, exclude_path=out_path)
    required = required_targets_for_chunk(ranges, targets, idxs, args.chunk, already_labeled)

    raw = sys.stdin.read() if args.json_file == "-" else Path(args.json_file).read_text(encoding="utf-8")
    try:
        submitted = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SubmitError(f"{args.json_file}: not valid JSON ({e})") from e
    if not isinstance(submitted, dict):
        raise SubmitError(f"{args.json_file}: expected a JSON object of "
                           f"{{text_key: label}}, got {type(submitted).__name__}")

    vocab = load_abelard_vocab()
    records = validate_submission(submitted, required, vocab)

    payload = {"conv": args.conv_guid, "model": "claude-interactive", "lines": records}
    if chunked:
        payload["chunk_size"] = chunk_size
        payload["chunk_overlap"] = overlap
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(records)} label(s) to {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("conv_guid")
    ap.add_argument("json_file", help="path to a JSON file, or '-' for stdin")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--chunk", type=int, default=0)
    ap.add_argument("--chunk-size", type=int, default=50)
    ap.add_argument("--chunk-overlap", type=int, default=10)
    ap.add_argument("--input", default=None, help="override conversations JSON (for testing)")
    args = ap.parse_args()
    try:
        run(args)
    except SubmitError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
