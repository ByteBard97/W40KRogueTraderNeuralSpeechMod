"""Pure logic for the interactive Abelard annotation harness: finding his unvoiced
target lines in a conversation, and splitting long conversations into readable,
tunable chunks. No file I/O - every caller owns its own path/data access, so this
module is trivially unit-testable with plain dicts."""
from __future__ import annotations


def abelard_targets(conv: dict) -> list[dict]:
    """Abelard's lines in `conv` that need a label: unvoiced (voiced absent or None),
    speaker.name == 'Abelard', with real text and a text_key. Document order, deduped
    by text_key within this conversation (first occurrence wins) - the real corpus has
    at least one conversation (LucidIdira_dialogue) with the same text_key appearing
    twice for Abelard, and every downstream dict/set keyed by text_key (target_indices,
    validate_submission's required_keys) silently breaks if a duplicate reaches it.
    Cross-conversation duplicates are a separate concern, handled by
    unlabeled_targets/scan_already_labeled_keys since they span different conv objects.

    This is the single source of truth for "how many lines need labeling" for a given
    conversation - never hardcode a count derived from it."""
    targets = []
    seen_keys = set()
    for line in conv.get("lines", []):
        speaker = line.get("speaker") or {}
        if speaker.get("name") != "Abelard":
            continue
        if line.get("voiced") is not None:
            continue
        if not line.get("text") or not line.get("text_key"):
            continue
        if line["text_key"] in seen_keys:
            continue
        seen_keys.add(line["text_key"])
        targets.append(line)
    return targets


def dialogue_lines(conv: dict) -> list[dict]:
    """Every line in `conv` (all speakers) with real text and a text_key, document
    order - the actual content shown when 'showing the whole conversation'."""
    return [line for line in conv.get("lines", []) if line.get("text") and line.get("text_key")]


def target_indices(dialogue: list[dict], targets: list[dict]) -> list[int]:
    """Position of each target line within `dialogue`, matched by text_key. When a
    text_key repeats in dialogue (a real corpus shape - LucidIdira_dialogue has this),
    the FIRST occurrence is used, matching abelard_targets' first-occurrence-wins
    dedup contract - a naive {key: i for ...} dict comprehension instead keeps the
    LAST occurrence, silently pointing a target at a different physical line than the
    one abelard_targets treats as canonical (found during Task 1's review, confirmed
    with a reproduction: two lines sharing text_key 'dup' at positions 2 and 5 - the
    naive version returns [5], not [2])."""
    index_by_key: dict[str, int] = {}
    for i, line in enumerate(dialogue):
        key = line.get("text_key")
        if key is not None and key not in index_by_key:
            index_by_key[key] = i
    return [index_by_key[t["text_key"]] for t in targets]


def validate_chunk_params(chunk_size: int, overlap: int) -> None:
    """Raise ValueError if these would make chunk_ranges's advance step <= 0 (infinite loop)."""
    if overlap >= chunk_size:
        raise ValueError(
            f"--chunk-overlap ({overlap}) must be less than --chunk-size ({chunk_size})"
        )


def chunk_ranges(lines: list[dict], target_indices: list[int],
                  chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """Split `lines` into (start, end) index ranges of at most chunk_size lines, with
    `overlap` lines shared between consecutive ranges, then drop any range that
    contains none of target_indices. A conversation at or under chunk_size is always a
    single (0, len(lines)) range - the whole thing, nothing dropped, nothing chunked."""
    validate_chunk_params(chunk_size, overlap)
    n = len(lines)
    if n <= chunk_size:
        return [(0, n)]
    ranges = []
    start = 0
    step = chunk_size - overlap
    while start < n:
        end = min(start + chunk_size, n)
        ranges.append((start, end))
        if end == n:
            break
        start += step
    return [r for r in ranges if any(r[0] <= idx < r[1] for idx in target_indices)]


def canonical_chunk(target_index: int, ranges: list[tuple[int, int]]) -> int:
    """Index into `ranges` of the first (lowest-index) range containing target_index -
    the one chunk that requires/accepts a submitted label for this target. Any other
    range containing it (via overlap) still renders it, but as already-labeled-
    elsewhere, not as a submission requirement."""
    for i, (start, end) in enumerate(ranges):
        if start <= target_index < end:
            return i
    raise ValueError(f"target_index {target_index} is not covered by any range in {ranges}")


def unlabeled_targets(targets: list[dict], already_labeled_keys: set[str]) -> list[dict]:
    """`targets` minus any whose text_key is already in already_labeled_keys. Some
    targets share a text_key with another target, including across different
    conversations, so a target can legitimately need this exclusion globally, not just
    within one conversation - see the design spec's 'Deduplication and canonical-chunk
    policy'."""
    return [t for t in targets if t["text_key"] not in already_labeled_keys]
