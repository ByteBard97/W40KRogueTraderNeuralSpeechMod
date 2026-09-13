# Interactive Abelard Annotation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a human (in practice, a Claude Code agent using real judgment) label Abelard's 572 unvoiced dialogue lines directly — with full conversational context — replacing the automated pass whose per-speaker filtering hides that context and produces weak labels.

**Architecture:** Two new CLI scripts (`interactive_next.py` shows the next conversation/chunk to label, `interactive_submit.py` validates and records labels) share a small pure-logic module (`context_window.py`) for finding Abelard's target lines and splitting oversized conversations into tunable, overlapping chunks. Output lands in a separate cache directory in the exact same file format the existing automated pipeline already uses, so `annotate.py --merge` and `diff_cache_vs_production.py` consume it with only a small, required fix to `annotate.py` (repeatable `--cache-dir`, since the existing merge rebuilds production from scratch out of only that directory's contents).

**Tech Stack:** Python 3, pytest, stdlib only (`json`, `hashlib`, `argparse`, `pathlib`) — no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-13-interactive-abelard-annotation-design.md` (this plan implements it in full; read it for the "why" behind decisions this plan states as fact — two rounds of review, including empirical verification against the real corpus, already happened before this plan was written).

## Global Constraints

- No new dependencies. In particular, do not add `jsonschema` — validation is hand-rolled (spec, "jsonschema" finding).
- Emotion validation uses `speaker_vocab.json["Abelard"]["words"]` (21 words), never the generic 12-word `schema.EMOTIONS`.
- `pace`/`nonverbal` validation reuses `schema.PACES`/`schema.NONVERBALS` exactly — do not redefine these lists.
- Cache file format for a single, unchunked conversation must exactly match what `annotate.py` already writes: `{"conv": <conv_guid>, "model": <string>, "lines": [{"guid": <text_key>, "emotion", "intensity", "pace", "nonverbal", "instruct", "text_hash"}]}`. A chunked conversation's cache file additionally carries top-level `"chunk_size"`/`"chunk_overlap"` keys.
- `text_hash` is computed identically to `annotate.py`'s `line_hash()`: `hashlib.sha1(text.encode()).hexdigest()[:12]`.
- Never hardcode "572" or "219" as a corpus size assumption in code — always derive from `abelard_targets()` over the live `conversations.enGB.json`.
- All new tests run via `python3 -m pytest` from `tools/annotate/` (the existing convention — no `conftest.py`, imports are bare module names like `from annotate import ...`).

---

### Task 1: `context_window.py` — pure logic for targets and chunking

**Files:**
- Create: `tools/annotate/context_window.py`
- Test: `tools/annotate/tests/test_context_window.py`

**Interfaces:**
- Produces: `abelard_targets(conv: dict) -> list[dict]`, `dialogue_lines(conv: dict) -> list[dict]`, `target_indices(dialogue: list[dict], targets: list[dict]) -> list[int]`, `validate_chunk_params(chunk_size: int, overlap: int) -> None` (raises `ValueError`), `chunk_ranges(lines: list[dict], target_indices: list[int], chunk_size: int, overlap: int) -> list[tuple[int, int]]`, `canonical_chunk(target_index: int, ranges: list[tuple[int, int]]) -> int`, `unlabeled_targets(targets: list[dict], already_labeled_keys: set[str]) -> list[dict]`. These are consumed by Task 3 and Task 4.

- [ ] **Step 1: Write the failing tests**

Create `tools/annotate/tests/test_context_window.py`:

```python
import pytest

from context_window import (
    abelard_targets, canonical_chunk, chunk_ranges, dialogue_lines,
    target_indices, unlabeled_targets, validate_chunk_params,
)


def _line(text_key, speaker_name=None, text="hi", voiced=None, has_speaker_key=True):
    line = {"guid": text_key, "kind": "cue", "text_key": text_key, "text": text, "voiced": voiced}
    if has_speaker_key:
        line["speaker"] = {"name": speaker_name} if speaker_name else {}
    return line


def _structural(guid):
    """An answers_list-style node: no text, no text_key - real shape from conversations.enGB.json."""
    return {"guid": guid, "kind": "answers_list", "parent": None}


def test_abelard_targets_finds_unvoiced_abelard_lines_with_text():
    conv = {"lines": [
        _line("a", "Abelard", voiced=None),
        _line("b", "Abelard", voiced="SomeCatalogEvent_01"),
        _line("c", "Idira", voiced=None),
    ]}
    assert {t["text_key"] for t in abelard_targets(conv)} == {"a"}


def test_abelard_targets_skips_structural_nodes():
    conv = {"lines": [_line("a", "Abelard"), _structural("x")]}
    assert {t["text_key"] for t in abelard_targets(conv)} == {"a"}


def test_abelard_targets_skips_lines_with_no_speaker_key():
    # 23,689 real lines lack a `speaker` key entirely - must not crash on it.
    conv = {"lines": [_line("a", has_speaker_key=False)]}
    assert abelard_targets(conv) == []


def test_abelard_targets_dedupes_intra_conversation_duplicate_text_key():
    # LucidIdira_dialogue has exactly this shape in the real corpus: the same text_key
    # appearing twice for Abelard within one conversation. Without deduping here,
    # target_indices' dict-based lookup collapses both to one index while
    # validate_submission still iterates both as separate list entries, writing two
    # records with the same guid into one cache file's "lines" array.
    conv = {"lines": [_line("dup", "Abelard", text="first"), _line("dup", "Abelard", text="first")]}
    assert len(abelard_targets(conv)) == 1


def test_dialogue_lines_includes_all_speakers_excludes_structural():
    conv = {"lines": [_line("a", "Abelard"), _line("b", "Idira"), _structural("x")]}
    assert {l["text_key"] for l in dialogue_lines(conv)} == {"a", "b"}


def test_target_indices_maps_targets_to_dialogue_positions():
    dialogue = [_line("a", "Idira"), _line("b", "Abelard"), _line("c", "Idira")]
    targets = [_line("b", "Abelard")]
    assert target_indices(dialogue, targets) == [1]


def test_chunk_ranges_whole_conversation_when_under_chunk_size():
    lines = [_line(str(i)) for i in range(10)]
    assert chunk_ranges(lines, target_indices=[3], chunk_size=50, overlap=10) == [(0, 10)]


def test_chunk_ranges_splits_long_conversation_with_overlap():
    lines = [_line(str(i)) for i in range(120)]
    # 10, 60, 100 each land in exactly one of the three raw ranges, so none get dropped
    ranges = chunk_ranges(lines, target_indices=[10, 60, 100], chunk_size=50, overlap=10)
    assert ranges == [(0, 50), (40, 90), (80, 120)]


def test_chunk_ranges_drops_ranges_with_no_target():
    lines = [_line(str(i)) for i in range(120)]
    ranges = chunk_ranges(lines, target_indices=[5], chunk_size=50, overlap=10)
    assert ranges == [(0, 50)]


def test_chunk_ranges_covers_every_line_index_with_no_gaps():
    # Regression guard for the empirical spec-review finding (0 of 572 real targets
    # dropped across all 219 conversations at the default 50/10 settings): if every
    # index is "a target", nothing may be silently excluded from every kept range.
    lines = [_line(str(i)) for i in range(150)]
    every_index = list(range(150))
    ranges = chunk_ranges(lines, target_indices=every_index, chunk_size=50, overlap=10)
    covered = set()
    for start, end in ranges:
        covered.update(range(start, end))
    assert covered == set(every_index)


def test_validate_chunk_params_rejects_overlap_at_or_above_chunk_size():
    with pytest.raises(ValueError):
        validate_chunk_params(chunk_size=50, overlap=50)
    with pytest.raises(ValueError):
        validate_chunk_params(chunk_size=50, overlap=60)


def test_validate_chunk_params_accepts_overlap_below_chunk_size():
    validate_chunk_params(chunk_size=50, overlap=10)  # must not raise


def test_canonical_chunk_single_range():
    assert canonical_chunk(5, [(0, 10)]) == 0


def test_canonical_chunk_picks_lower_index_in_overlap():
    ranges = [(0, 50), (40, 90)]
    assert canonical_chunk(45, ranges) == 0  # in both ranges - lower (earlier) wins


def test_canonical_chunk_raises_if_index_not_covered():
    with pytest.raises(ValueError):
        canonical_chunk(100, [(0, 50)])


def test_unlabeled_targets_excludes_already_labeled_keys():
    targets = [_line("a", "Abelard"), _line("b", "Abelard")]
    result = unlabeled_targets(targets, already_labeled_keys={"a"})
    assert {t["text_key"] for t in result} == {"b"}


def test_unlabeled_targets_empty_labeled_set_is_noop():
    targets = [_line("a", "Abelard")]
    assert unlabeled_targets(targets, already_labeled_keys=set()) == targets
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/annotate && python3 -m pytest tests/test_context_window.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'context_window'`

- [ ] **Step 3: Write `context_window.py`**

```python
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
    """Position of each target line within `dialogue`, matched by text_key."""
    index_by_key = {line["text_key"]: i for i, line in enumerate(dialogue)}
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
    """`targets` minus any whose text_key is already in already_labeled_keys. 13 of the
    572 real Abelard targets share a text_key with another target (6 across different
    conversations), so a target can legitimately need this exclusion globally, not just
    within one conversation - see the design spec's 'Deduplication and canonical-chunk
    policy'."""
    return [t for t in targets if t["text_key"] not in already_labeled_keys]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/annotate && python3 -m pytest tests/test_context_window.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tools/annotate/context_window.py tools/annotate/tests/test_context_window.py
git commit -m "Add context_window.py: pure target-finding/chunking logic for interactive annotation"
```

---

### Task 2: Fix `annotate.py --merge` and `diff_cache_vs_production.py` — repeatable cache dirs, deterministic ordering

**Files:**
- Modify: `tools/annotate/annotate.py:210` (argparse), `:226-227` (cache dir setup), `:247-257` (merge block), `:270` (per-conversation cache write path)
- Modify: `tools/annotate/diff_cache_vs_production.py` (replace `load_cache` entirely with a call to `annotate.merge_cache_dirs`; `cache_dir` argument becomes `nargs="+"`)
- Modify: `tools/annotate/tests/test_annotate.py` (append new tests)
- Create: `tools/annotate/tests/test_diff_cache_vs_production.py`

**Interfaces:**
- Produces: `annotate.merge_cache_dirs(cache_dirs: list[Path]) -> tuple[dict, int]` (merged annotation dict, count of cache files read) — new, extracted from the inline `--merge` block so it's directly testable, and reused by `diff_cache_vs_production.py` so there is exactly one implementation of "merge N cache directories" in the codebase.
- Consumes: nothing from Task 1; independent of it.

**Context — why this task exists, and a critical fact found only by running code against the real repo, not by reading `annotate.py`'s comments:** `annotate.py --merge` currently rebuilds `annotations.enGB.json` from scratch out of *only* `--cache-dir`'s contents. Pointed at an Abelard-only cache directory, it would silently overwrite the rest of the corpus. Fixing this is required before Task 3/4's output can ever be safely merged.

**`data/annotations/cache` (this file's own default) is *not* the full corpus.** Verified directly: it has 200 files / 5,599 guids. `data/annotations/cache_merged` has 1,328 files / 45,114 guids — an exact key-set match with shipped `annotations.enGB.json`. Every real merge in this project must name `cache_merged` explicitly; never rely on the code's own default for a real merge. (Two earlier spec-review rounds assumed the default was correct from the code's own comment, without checking — this was caught only when a plan reviewer actually ran `merge_cache_dirs` against both directories and compared guid counts. **Step 6 of this task repeats that exact check** so it's never re-assumed again.)

While touching this code, also fix a second, independent, pre-existing bug: `cache_dir.glob("*.json")` iterates in arbitrary filesystem order, and `cache_merged` has 1,680 duplicate `text_key`s across its files, meaning today's merge already picks an arbitrary winner for those, nondeterministically. `sorted()` fixes this — but **verified directly against real data, applying it is not a no-op**: a `sorted()` merge of `cache_merged` alone (followed by `reconcile_sarcasm_emotion`, exactly like a real `--merge` run), diffed against today's shipped `annotations.enGB.json`, changes 487 of the 45,114 records — 115 of them in `emotion` — because sorted-filename order picks a different deterministic winner than historical scandir order did for some of those 1,680 collisions. Fixing the bug is still correct (a reproducible result beats an accidental one), but this must be surfaced to a human before it's ever applied to production, not silently absorbed into a merge that also happens to add Abelard's work. **Step 7 below produces that preview and stops there — it does not run a real merge.**

- [ ] **Step 1: Write the failing tests**

Append to `tools/annotate/tests/test_annotate.py`:

```python
import json

from annotate import merge_cache_dirs


def _write_cache_file(path, conv_guid, text_key, emotion):
    path.write_text(json.dumps({
        "conv": conv_guid, "model": "test",
        "lines": [{"guid": text_key, "emotion": emotion, "intensity": 0.5,
                   "pace": "normal", "nonverbal": [], "instruct": "x", "text_hash": "abc123"}],
    }), encoding="utf-8")


def test_merge_cache_dirs_single_dir(tmp_path):
    d = tmp_path / "cache"
    d.mkdir()
    _write_cache_file(d / "conv1.json", "conv1", "key1", "neutral")
    merged, file_count = merge_cache_dirs([d])
    assert merged["key1"]["emotion"] == "neutral"
    assert file_count == 1


def test_merge_cache_dirs_later_dir_wins_on_conflict(tmp_path):
    d1, d2 = tmp_path / "cache1", tmp_path / "cache2"
    d1.mkdir()
    d2.mkdir()
    _write_cache_file(d1 / "conv1.json", "conv1", "key1", "neutral")
    _write_cache_file(d2 / "conv1.json", "conv1", "key1", "angry")
    merged, _ = merge_cache_dirs([d1, d2])
    assert merged["key1"]["emotion"] == "angry"


def test_merge_cache_dirs_guid_in_only_one_dir_passes_through(tmp_path):
    d1, d2 = tmp_path / "cache1", tmp_path / "cache2"
    d1.mkdir()
    d2.mkdir()
    _write_cache_file(d1 / "conv1.json", "conv1", "key1", "neutral")
    _write_cache_file(d2 / "conv2.json", "conv2", "key2", "angry")
    merged, _ = merge_cache_dirs([d1, d2])
    assert merged["key1"]["emotion"] == "neutral"
    assert merged["key2"]["emotion"] == "angry"


def test_merge_cache_dirs_duplicate_guid_within_one_dir_is_deterministic_by_filename(tmp_path):
    # Regression test for the sorted() fix - mirrors cache_merged's real 1,680 duplicate
    # text_keys, where today's merge picks an arbitrary winner. sorted() processes
    # conv_a.json before conv_z.json, so conv_z's value (processed last) always wins,
    # regardless of the order the files happened to be created on disk.
    d = tmp_path / "cache"
    d.mkdir()
    _write_cache_file(d / "conv_z.json", "conv_z", "dupkey", "angry")
    _write_cache_file(d / "conv_a.json", "conv_a", "dupkey", "sad")
    merged, _ = merge_cache_dirs([d])
    assert merged["dupkey"]["emotion"] == "angry"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/annotate && python3 -m pytest tests/test_annotate.py -v`
Expected: the new tests FAIL with `ImportError: cannot import name 'merge_cache_dirs'`.

- [ ] **Step 3: Fix `annotate.py`**

Read the current file first — `tools/annotate/annotate.py` — to get exact line numbers, since line numbers below are from the version read during spec-writing and may have shifted slightly.

Change the argparse line (currently `annotate.py:210`):

```python
    ap.add_argument("--cache-dir", default=None, help="override cache dir (default data/annotations/cache)")
```

to:

```python
    ap.add_argument("--cache-dir", action="append", default=None,
                    help="override cache dir (default data/annotations/cache - NOTE: this "
                         "default is NOT the full corpus, use data/annotations/cache_merged "
                         "for a real merge); repeatable - later directories take precedence "
                         "over earlier ones for a given guid when merging, and the LAST "
                         "directory given is where an annotation run writes its own cache files")
```

Change the cache-dir setup (currently `annotate.py:226-227`):

```python
    cache_dir = Path(args.cache_dir) if args.cache_dir else CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
```

to:

```python
    cache_dirs = [Path(d) for d in args.cache_dir] if args.cache_dir else [CACHE]
    for d in cache_dirs:
        d.mkdir(parents=True, exist_ok=True)
    write_cache_dir = cache_dirs[-1]
```

Add this new function just above `def main() -> None:`:

```python
def merge_cache_dirs(cache_dirs: list[Path]) -> tuple[dict, int]:
    """Merge every cache-dir's *.json files (sorted within each dir for determinism -
    cache_merged alone has 1,680 duplicate text_keys across its files, so unsorted glob
    order already picks an arbitrary winner for those), later directories' entries
    overriding earlier ones on a guid conflict. Returns (merged_dict, file_count)."""
    merged: dict = {}
    file_count = 0
    for d in cache_dirs:
        for f in sorted(d.glob("*.json")):
            file_count += 1
            for r in json.load(open(f, encoding="utf-8"))["lines"]:
                merged[r["guid"]] = {k: v for k, v in r.items() if k != "guid"}
    return merged, file_count
```

Replace the `--merge` block (currently `annotate.py:247-257`):

```python
    if args.merge:
        merged = {}
        for f in cache_dir.glob("*.json"):
            for r in json.load(open(f, encoding="utf-8"))["lines"]:
                merged[r["guid"]] = {k: v for k, v in r.items() if k != "guid"}
        fixed = reconcile_sarcasm_emotion(merged)
        out = ROOT / "data/annotations/annotations.enGB.json"
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"merged {len(merged)} annotations from {len(list(cache_dir.glob('*.json')))} conversations -> {out}")
        print(f"reconciled emotion->sarcastic on {fixed} lines whose instruct text implied sarcasm/mockery")
        return
```

with:

```python
    if args.merge:
        merged, file_count = merge_cache_dirs(cache_dirs)
        fixed = reconcile_sarcasm_emotion(merged)
        out = ROOT / "data/annotations/annotations.enGB.json"
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"merged {len(merged)} annotations from {file_count} cache files across "
              f"{len(cache_dirs)} director{'y' if len(cache_dirs) == 1 else 'ies'} -> {out}")
        print(f"reconciled emotion->sarcastic on {fixed} lines whose instruct text implied sarcasm/mockery")
        return
```

Change the per-conversation cache write path (currently `annotate.py:270`, inside the annotation-run loop):

```python
        cache_file = cache_dir / f"{conv['guid']}.json"
```

to:

```python
        cache_file = write_cache_dir / f"{conv['guid']}.json"
```

- [ ] **Step 4: Refactor `diff_cache_vs_production.py` to reuse `merge_cache_dirs` instead of keeping its own parallel `load_cache`**

This file previously had its own `load_cache(cache_dir)` with the identical unsorted-glob gap, only ever accepting one directory. Keeping two independent copies of "merge N cache directories" is exactly the kind of duplication that let both this bug and the `cache`-vs-`cache_merged` mistake go unnoticed for two review rounds — so this file now imports and calls `annotate.merge_cache_dirs` directly, and accepts one or more directories itself (needed for the Step 7 preview below, which must simulate a *multi*-directory merge before it's ever run for real).

Read the current `tools/annotate/diff_cache_vs_production.py` first. Replace its `load_cache` function and the top of `main()`:

```python
def load_cache(cache_dir: Path) -> dict:
    merged = {}
    for f in cache_dir.glob("*.json"):
        for r in json.load(open(f, encoding="utf-8"))["lines"]:
            merged[r["guid"]] = r
    return merged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    production = json.loads((ROOT / "data/annotations/annotations.enGB.json").read_text(encoding="utf-8"))
    pilot = load_cache(Path(args.cache_dir))
```

with:

```python
import sys

sys.path.insert(0, str(Path(__file__).parent))
from annotate import merge_cache_dirs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir", nargs="+",
                    help="one or more cache directories, later ones taking precedence on "
                         "a guid conflict - same semantics as annotate.py --merge")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    production = json.loads((ROOT / "data/annotations/annotations.enGB.json").read_text(encoding="utf-8"))
    pilot, _ = merge_cache_dirs([Path(d) for d in args.cache_dir])
```

(Move the `import sys` to the top of the file with the other imports rather than mid-file if the existing file's import block makes that cleaner — the exact placement doesn't matter, only that it's imported once.)

The rest of `main()` (the `common`/`new_only`/`changed`/`unchanged` computation and report-writing) is unchanged — it already only reads from `pilot`/`production`, both still plain dicts.

Also update the two remaining references to `args.cache_dir` later in `main()` (the report title and the default `--out` filename), which currently assume a single string:

```python
    lines = [f"# Pilot review: {Path(args.cache_dir).name}", "",
```

to:

```python
    lines = [f"# Pilot review: {'+'.join(Path(d).name for d in args.cache_dir)}", "",
```

and:

```python
    out = Path(args.out) if args.out else ROOT / f"data/annotations/{Path(args.cache_dir).name}_review.md"
```

to:

```python
    out = Path(args.out) if args.out else ROOT / f"data/annotations/{'_'.join(Path(d).name for d in args.cache_dir)}_review.md"
```

- [ ] **Step 5: Write a small test for the new multi-directory wiring**

Create `tools/annotate/tests/test_diff_cache_vs_production.py` — this only needs to prove the re-exported `merge_cache_dirs` import actually works from this module; the merge logic itself is already fully covered by Step 1's tests on the original in `annotate.py`. (`diff_cache_vs_production.py`'s `ROOT` and production-file path are resolved from `__file__` at import time with no override argument, unlike `interactive_submit.py`'s `--input`, so a full `main()` invocation isn't easily testable here without monkeypatching a module constant — not worth it for what would be a duplicate of Step 1's coverage.)

```python
import json

from diff_cache_vs_production import merge_cache_dirs


def _write_cache_file(path, text_key, emotion):
    path.write_text(json.dumps({
        "conv": "c", "model": "test",
        "lines": [{"guid": text_key, "emotion": emotion, "intensity": 0.5,
                   "pace": "normal", "nonverbal": [], "instruct": "x", "text_hash": "abc123"}],
    }), encoding="utf-8")


def test_merge_cache_dirs_is_reexported_and_later_dir_wins(tmp_path):
    # diff_cache_vs_production.py imports merge_cache_dirs from annotate rather than
    # defining its own - this just confirms the import/re-export actually works and
    # behaves identically to Task 2 Step 1's tests on the original.
    d1, d2 = tmp_path / "cache1", tmp_path / "cache2"
    d1.mkdir()
    d2.mkdir()
    _write_cache_file(d1 / "conv1.json", "key1", "neutral")
    _write_cache_file(d2 / "conv1.json", "key1", "angry")
    merged, _ = merge_cache_dirs([d1, d2])
    assert merged["key1"]["emotion"] == "angry"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd tools/annotate && python3 -m pytest tests/test_annotate.py tests/test_diff_cache_vs_production.py tests/test_schema.py -v`
Expected: All PASS (including every pre-existing `test_annotate.py` test — this change must not break `conv_payload`/`validate`/`build_system`, which are untouched).

- [ ] **Step 7: Manually verify `cache_merged` vs `cache`, and preview the `sorted()` fix's real effect on production — do not run a real merge**

First, confirm the critical fact this task's "Context" section states, on this machine, right now:
```bash
cd tools/annotate && python3 -c "
from pathlib import Path
from annotate import merge_cache_dirs
for name in ('cache', 'cache_merged'):
    merged, count = merge_cache_dirs([Path(f'../../data/annotations/{name}')])
    print(f'{name}: {count} files, {len(merged)} guids')
"
```
Expected: `cache: 200 files, 5599 guids` and `cache_merged: 1328 files, 45114 guids`. If `cache_merged`'s guid count doesn't match `data/annotations/annotations.enGB.json`'s entry count, stop and investigate before proceeding to any real merge — the rest of this project's merge story depends on `cache_merged` being the correct source.

Then preview the `sorted()` fix's real effect on production. **Do not use `diff_cache_vs_production.py` for this specific preview** — it only ever compares the `emotion` field (never the full record) and never applies `reconcile_sarcasm_emotion`, so pointed at a raw `sorted()` merge it would report 312 emotion changes, not the 487-all-field/115-emotion figure a *real* `--merge` run actually produces (`reconcile_sarcasm_emotion` closes 197 of those 312 apparent gaps by flipping both sides to `sarcastic`, since it runs on the merged side both times in a real merge but never runs on the diff tool's raw pilot input). Changing `diff_cache_vs_production.py` itself to always apply `reconcile_sarcasm_emotion` is out of scope here — it's a general-purpose pilot-review tool with its own existing tests and use case (Task 2 doesn't change its comparison semantics, only its directory-handling). Instead, run this one-off snippet, which reproduces exactly what a real `--merge` run would produce and diffs every field, not just `emotion`:
```bash
cd tools/annotate && python3 -c "
import json
from annotate import merge_cache_dirs, reconcile_sarcasm_emotion

merged, _ = merge_cache_dirs(['../../data/annotations/cache_merged'])
reconcile_sarcasm_emotion(merged)
production = json.loads(open('../../data/annotations/annotations.enGB.json').read())

common = [g for g in merged if g in production]
changed = [g for g in common if merged[g] != production[g]]
emotion_changed = [g for g in changed if merged[g]['emotion'] != production[g]['emotion']]
print(f'{len(changed)} of {len(common)} records differ from shipped production after the sorted() fix')
print(f'{len(emotion_changed)} of those differ in emotion specifically')
print()
print('first 5 emotion changes:')
for g in emotion_changed[:5]:
    print(f'  {g}: {production[g][\"emotion\"]!r} -> {merged[g][\"emotion\"]!r}')
"
```
Expected: `487 of 45114 records differ ... 115 of those differ in emotion` (matches this task's "Context" section, verified independently, twice, before this plan was written). **This is expected and is not a bug to fix** — it's the real, human-reviewable cost of making the merge deterministic; the alternative is keeping an arbitrary, unreproducible historical accident. Skim the printed examples and confirm they look like reasonable alternate labels (not garbage), then tell the user this preview exists and that a human should look at the full list before the *first* real merge under this fixed code is ever run — that real merge is explicitly out of scope for this plan (see spec Non-goals: "Not auto-merging into `annotations.enGB.json`"). If a fuller reviewable table is wanted, redirect the snippet's per-`g` loop (drop the `[:5]`) to a file instead of printing 115 lines to the terminal.

- [ ] **Step 8: Commit**

```bash
git add tools/annotate/annotate.py tools/annotate/diff_cache_vs_production.py tools/annotate/tests/test_annotate.py tools/annotate/tests/test_diff_cache_vs_production.py
git commit -m "Make annotate.py --merge safe for multiple cache dirs, fix nondeterministic merge order"
```

---

### Task 3: `interactive_submit.py` — validate and record labels

**Files:**
- Create: `tools/annotate/interactive_submit.py`
- Test: `tools/annotate/tests/test_interactive_submit.py`

**Interfaces:**
- Consumes from Task 1: `abelard_targets`, `canonical_chunk`, `chunk_ranges`, `dialogue_lines`, `target_indices`, `validate_chunk_params` (all from `context_window`).
- Consumes from `tools/annotate/schema.py` (unchanged): `PACES`, `NONVERBALS`.
- Produces: `SubmitError` (exception class), `find_conversation(convs, conv_guid) -> dict`, `resolve_chunk_params(cache_dir, conv_guid, cli_chunk_size, cli_overlap) -> tuple[int, int]`, `scan_already_labeled_keys(cache_dir, exclude_path=None) -> set[str]`, `required_targets_for_chunk(ranges, targets, idxs, chunk, already_labeled=frozenset()) -> list[dict]`, `validate_submission(submitted, required, vocab) -> list[dict]`, `run(args) -> None` — all consumed only by this script's own tests and CLI entry point; Task 4 does not import from this file (it duplicates the small `resolve_chunk_params`/`scan_already_labeled_keys` helpers rather than cross-import a sibling CLI script — see Task 4's note).

**Note on why `already_labeled` matters here, not just in `interactive_next.py`:** a target already labeled via a different conversation (13 of 572 targets share a `text_key` with another target, 6 across different conversations) must not be *required* in this chunk's submission either — `interactive_next.py` already excludes it from what it tells Claude to submit, so requiring it here would make every such conversation permanently unsubmittable (`missing: <key>` forever). This was found during a second plan-review pass, after the first draft of this script computed its required-target set with no awareness of what had already been labeled elsewhere.

- [ ] **Step 1: Write the failing tests**

Create `tools/annotate/tests/test_interactive_submit.py`:

```python
import argparse
import hashlib
import json

import pytest

from interactive_submit import (
    SubmitError, find_conversation, required_targets_for_chunk,
    resolve_chunk_params, run, scan_already_labeled_keys, validate_submission,
)

VOCAB = ["resigned", "hopeful", "neutral", "sarcastic"]


def _target(text_key, text="hi", speaker_name="Abelard"):
    return {"guid": text_key, "kind": "cue", "text_key": text_key, "text": text,
            "speaker": {"name": speaker_name}, "voiced": None}


def _label(emotion="resigned", intensity=0.5, pace="normal", nonverbal=None, instruct="x"):
    return {"emotion": emotion, "intensity": intensity, "pace": pace,
            "nonverbal": nonverbal or [], "instruct": instruct}


def _sha1_12(text):
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def test_find_conversation_returns_matching_conv():
    convs = [{"guid": "a"}, {"guid": "b"}]
    assert find_conversation(convs, "b") == {"guid": "b"}


def test_find_conversation_raises_for_unknown_guid():
    with pytest.raises(SubmitError):
        find_conversation([{"guid": "a"}], "missing")


def test_required_targets_for_chunk_filters_by_canonical_chunk():
    targets = [_target("a"), _target("b")]
    ranges = [(0, 50), (40, 90)]
    idxs = [10, 60]  # a canonical to chunk 0, b canonical to chunk 1
    assert [t["text_key"] for t in required_targets_for_chunk(ranges, targets, idxs, 0)] == ["a"]
    assert [t["text_key"] for t in required_targets_for_chunk(ranges, targets, idxs, 1)] == ["b"]


def test_required_targets_for_chunk_rejects_out_of_range_chunk():
    with pytest.raises(SubmitError):
        required_targets_for_chunk([(0, 50)], [_target("a")], [10], chunk=5)


def test_required_targets_for_chunk_rejects_negative_chunk():
    # Without this, a negative chunk would never equal any real canonical_chunk() result
    # (always >= 0), so required silently comes back empty and the eventual error is a
    # confusing "unexpected guids" instead of a clear "chunk does not exist".
    with pytest.raises(SubmitError, match="does not exist"):
        required_targets_for_chunk([(0, 50)], [_target("a")], [10], chunk=-1)


def test_required_targets_for_chunk_excludes_already_labeled_targets():
    # A target already labeled via a different conversation (a cross-conversation
    # duplicate text_key) must not be required here either - see this task's note on
    # why, and context_window.unlabeled_targets in Task 1.
    targets = [_target("a"), _target("b")]
    ranges = [(0, 50)]
    idxs = [10, 20]
    required = required_targets_for_chunk(ranges, targets, idxs, 0, already_labeled={"a"})
    assert [t["text_key"] for t in required] == ["b"]


def test_required_targets_for_chunk_default_already_labeled_is_empty():
    targets = [_target("a")]
    required = required_targets_for_chunk([(0, 50)], targets, [10], 0)
    assert [t["text_key"] for t in required] == ["a"]


def test_validate_submission_happy_path_returns_records_with_text_hash():
    required = [_target("a", text="hello")]
    submitted = {"a": _label()}
    records = validate_submission(submitted, required, VOCAB)
    assert len(records) == 1
    assert records[0]["guid"] == "a"
    assert records[0]["text_hash"] == _sha1_12("hello")


def test_validate_submission_rejects_non_dict_label():
    # {"a": "resigned"} instead of {"a": {"emotion": "resigned", ...}} would otherwise
    # crash on rec.get(...) with an AttributeError instead of a clean SubmitError.
    required = [_target("a")]
    submitted = {"a": "resigned"}
    with pytest.raises(SubmitError, match="JSON object"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_missing_guid():
    required = [_target("a"), _target("b")]
    submitted = {"a": _label()}
    with pytest.raises(SubmitError, match="missing"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_unexpected_guid():
    required = [_target("a")]
    submitted = {"a": _label(), "z": _label()}
    with pytest.raises(SubmitError, match="unexpected"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_emotion_not_in_vocab():
    required = [_target("a")]
    submitted = {"a": _label(emotion="made_up")}
    with pytest.raises(SubmitError, match="vocabulary"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_bad_pace():
    required = [_target("a")]
    submitted = {"a": _label(pace="ludicrous")}
    with pytest.raises(SubmitError, match="pace"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_bad_nonverbal():
    required = [_target("a")]
    submitted = {"a": _label(nonverbal=["screaming"])}
    with pytest.raises(SubmitError, match="nonverbal"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_out_of_range_intensity():
    required = [_target("a")]
    submitted = {"a": _label(intensity=1.5)}
    with pytest.raises(SubmitError, match="intensity"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_empty_instruct():
    required = [_target("a")]
    submitted = {"a": _label(instruct="")}
    with pytest.raises(SubmitError, match="instruct"):
        validate_submission(submitted, required, VOCAB)


def test_validate_submission_rejects_too_long_instruct():
    required = [_target("a")]
    submitted = {"a": _label(instruct="x" * 301)}
    with pytest.raises(SubmitError, match="300"):
        validate_submission(submitted, required, VOCAB)


def test_scan_already_labeled_keys_reads_every_cache_file(tmp_path):
    (tmp_path / "conv1.json").write_text(json.dumps({
        "conv": "conv1", "model": "m", "lines": [{"guid": "a", "emotion": "resigned"}],
    }), encoding="utf-8")
    (tmp_path / "conv2__chunk0.json").write_text(json.dumps({
        "conv": "conv2", "model": "m", "lines": [{"guid": "b", "emotion": "resigned"}],
        "chunk_size": 50, "chunk_overlap": 10,
    }), encoding="utf-8")
    assert scan_already_labeled_keys(tmp_path) == {"a", "b"}


def test_scan_already_labeled_keys_excludes_given_path(tmp_path):
    # Resubmitting/correcting the same chunk must not see its own about-to-be-
    # overwritten file as "already labeled elsewhere", or every key in it becomes
    # unexpected on the very next resubmission attempt.
    target_path = tmp_path / "conv1.json"
    target_path.write_text(json.dumps({
        "conv": "conv1", "model": "m", "lines": [{"guid": "a", "emotion": "resigned"}],
    }), encoding="utf-8")
    assert scan_already_labeled_keys(tmp_path, exclude_path=target_path) == set()


def test_resolve_chunk_params_uses_cli_when_no_existing_chunks(tmp_path):
    assert resolve_chunk_params(tmp_path, "conv1", 50, 10) == (50, 10)


def test_resolve_chunk_params_reuses_recorded_values(tmp_path):
    (tmp_path / "conv1__chunk0.json").write_text(json.dumps({
        "conv": "conv1", "model": "claude-interactive", "lines": [],
        "chunk_size": 30, "chunk_overlap": 5,
    }), encoding="utf-8")
    assert resolve_chunk_params(tmp_path, "conv1", 50, 10) == (30, 5)


def _args(**overrides):
    defaults = dict(conv_guid="conv1", json_file=None, cache_dir=None, chunk=0,
                     chunk_size=50, chunk_overlap=10, input=None)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_run_rejects_malformed_json_with_a_clean_error_not_a_traceback(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "TestConv", "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text("{not valid json", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    with pytest.raises(SubmitError, match="not valid JSON"):
        run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))
    assert not (cache_dir / "conv1.json").exists()


def test_run_rejects_a_json_list_instead_of_an_object(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "TestConv", "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text("[1, 2, 3]", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    with pytest.raises(SubmitError, match="expected a JSON object"):
        run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))


def test_run_writes_unchunked_cache_file_for_small_conversation(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "TestConv",
        "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"a": _label()}), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))

    out = json.loads((cache_dir / "conv1.json").read_text(encoding="utf-8"))
    assert out["conv"] == "conv1"
    assert out["model"] == "claude-interactive"
    assert out["lines"][0]["guid"] == "a"
    assert out["lines"][0]["text_hash"] == _sha1_12("hello")
    assert "chunk_size" not in out


def test_run_writes_chunked_cache_file_with_chunk_params_recorded(tmp_path):
    lines = [_target(f"key{i}", text=f"line {i}", speaker_name="Idira") for i in range(120)]
    lines[10] = _target("key10", text="line 10")   # Abelard - lands in chunk range (0, 50)
    lines[100] = _target("key100", text="line 100")  # Abelard - lands in chunk range (80, 120)
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{"guid": "conv1", "name": "TestConv", "lines": lines}]),
                           encoding="utf-8")
    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"key10": _label()}), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir),
              input=str(convs_path), chunk=0))

    out_path = cache_dir / "conv1__chunk0.json"
    assert out_path.exists()
    out = json.loads(out_path.read_text(encoding="utf-8"))
    assert out["chunk_size"] == 50
    assert out["chunk_overlap"] == 10
    assert out["lines"][0]["guid"] == "key10"


def test_run_excludes_target_already_labeled_in_a_different_conversation(tmp_path):
    # Reproduces the real corpus shape (e.g. AlternativeLordCaptains_dialogue /
    # AlternativeLordCaptains_Fem_dialogue sharing three text_keys): "sharedkey" was
    # already labeled while working through conv1; conv2 reuses the same text_key
    # alongside its own "onlyinconv2" - submitting conv2 must not require "sharedkey"
    # again, and must not choke trying to write a second copy of it.
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([
        {"guid": "conv1", "name": "Conv1", "lines": [_target("sharedkey", text="shared")]},
        {"guid": "conv2", "name": "Conv2", "lines": [
            _target("sharedkey", text="shared"),
            _target("onlyinconv2", text="only here"),
        ]},
    ]), encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "conv1.json").write_text(json.dumps({
        "conv": "conv1", "model": "claude-interactive",
        "lines": [{"guid": "sharedkey", "emotion": "resigned", "intensity": 0.4,
                   "pace": "normal", "nonverbal": [], "instruct": "x", "text_hash": "x"}],
    }), encoding="utf-8")

    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"onlyinconv2": _label()}), encoding="utf-8")

    run(_args(conv_guid="conv2", json_file=str(submitted_path),
              cache_dir=str(cache_dir), input=str(convs_path)))

    out = json.loads((cache_dir / "conv2.json").read_text(encoding="utf-8"))
    assert [line["guid"] for line in out["lines"]] == ["onlyinconv2"]


def test_run_resubmitting_same_chunk_does_not_treat_its_own_prior_output_as_a_conflict(tmp_path):
    convs_path = tmp_path / "convs.json"
    convs_path.write_text(json.dumps([{
        "guid": "conv1", "name": "Conv1", "lines": [_target("a", text="hello")],
    }]), encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    # A prior (imperfect) submission already exists for this exact chunk.
    (cache_dir / "conv1.json").write_text(json.dumps({
        "conv": "conv1", "model": "claude-interactive",
        "lines": [{"guid": "a", "emotion": "resigned", "intensity": 0.3,
                   "pace": "slow", "nonverbal": [], "instruct": "old", "text_hash": "x"}],
    }), encoding="utf-8")

    submitted_path = tmp_path / "submitted.json"
    submitted_path.write_text(json.dumps({"a": _label(emotion="hopeful")}), encoding="utf-8")

    run(_args(json_file=str(submitted_path), cache_dir=str(cache_dir), input=str(convs_path)))

    out = json.loads((cache_dir / "conv1.json").read_text(encoding="utf-8"))
    assert out["lines"][0]["emotion"] == "hopeful"  # corrected value, not silently skipped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tools/annotate && python3 -m pytest tests/test_interactive_submit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'interactive_submit'`

- [ ] **Step 3: Write `interactive_submit.py`**

```python
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
    excluded here; so is a target already labeled via a different conversation (13 of
    572 real targets share a text_key with another target, 6 across different
    conversations) - requiring it again here would make that conversation permanently
    unsubmittable."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tools/annotate && python3 -m pytest tests/test_interactive_submit.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add tools/annotate/interactive_submit.py tools/annotate/tests/test_interactive_submit.py
git commit -m "Add interactive_submit.py: validate and record interactive Abelard labels"
```

---

### Task 4: `interactive_next.py` — show the next conversation/chunk to label

**Files:**
- Create: `tools/annotate/interactive_next.py`

**Interfaces:**
- Consumes from Task 1: `abelard_targets`, `canonical_chunk`, `chunk_ranges`, `dialogue_lines`, `target_indices`, `unlabeled_targets`, `validate_chunk_params` (all from `context_window`).
- Does not consume from Task 3 (`interactive_submit.py`) — `resolve_chunk_params` is duplicated here rather than cross-imported from a sibling CLI script, since it's ~8 lines and each script should be independently runnable without importing the other.
- No automated tests for this file per the spec ("cheap enough to spot check visually... its scan/skip logic is exercised transitively by `test_context_window.py`") — verification is a manual smoke test against real data (Step 3 below).

- [ ] **Step 1: Write `interactive_next.py`**

```python
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
CONVERSATIONS_PATH = ROOT / "data/conversations.enGB.json"
BIOS_PATH = ROOT / "data/character_bios.json"
VOCAB_PATH = ROOT / "data/voices/emotion_banks/speaker_vocab.json"
# Derived from schema.py, never redefined by hand - see the plan's Global Constraints.
PACES_LINE = "Paces: " + ", ".join(PACES)
NONVERBAL_LINE = "Nonverbal (optional): " + ", ".join(NONVERBALS)


def scan_already_labeled_keys(cache_dir: Path) -> set[str]:
    """Every text_key with a label anywhere in cache_dir, across every conversation's
    cache file - the global dedup set (see context_window.unlabeled_targets)."""
    keys = set()
    for f in cache_dir.glob("*.json"):
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
           already_labeled: set[str], bios: dict, vocab: list[str]) -> str:
    dialogue = dialogue_lines(conv)
    all_targets = abelard_targets(conv)
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
    footer.append(f"Submit with: interactive_submit.py {conv['guid']}{chunk_flag} <json-file>")
    return "\n".join(header + body + footer)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("conv_guid", nargs="?", default=None)
    ap.add_argument("chunk_index", nargs="?", type=int, default=0)
    ap.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    ap.add_argument("--chunk-size", type=int, default=50)
    ap.add_argument("--chunk-overlap", type=int, default=10)
    args = ap.parse_args()

    validate_chunk_params(args.chunk_size, args.chunk_overlap)
    cache_dir = Path(args.cache_dir)
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
        all_targets = abelard_targets(conv)
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
        print(render(conv, args.chunk_index, chunk_size, overlap, already_labeled, bios, vocab))
        return

    for conv in convs:
        all_targets = abelard_targets(conv)
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
        print(render(conv, chunk_index, chunk_size, overlap, already_labeled, bios, vocab))
        return

    print("Nothing left to label - every Abelard target has a cache entry.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manually verify against real data — nothing labeled yet**

Run:
```bash
cd tools/annotate && python3 interactive_next.py --cache-dir /tmp/abelard_smoketest
```
Expected: prints a real conversation (the first one in `conversations.enGB.json` containing an Abelard unvoiced target), with a bio line, a 21-word vocabulary line, at least one `>>>`-marked line, and a `Submit with: ...` footer. No `···` lines yet (nothing labeled). No crash.

- [ ] **Step 3: Manually verify the submit → next round-trip**

Using the actual conversation guid and target guid(s) printed in Step 2, write a small labels file and submit it:
```bash
cd tools/annotate
echo '{"<paste the first target guid from Step 2 here>": {"emotion": "resigned", "intensity": 0.4, "pace": "normal", "nonverbal": [], "instruct": "Quiet, formal resignation."}}' > /tmp/test_labels.json
python3 interactive_submit.py --cache-dir /tmp/abelard_smoketest <paste the conv guid> /tmp/test_labels.json
python3 interactive_next.py --cache-dir /tmp/abelard_smoketest
```
Expected: `interactive_submit.py` prints `wrote 1 label(s) to ...`; the second `interactive_next.py` call either shows the *next* conversation (if that one had only one target) or the same conversation with the just-labeled line now marked `···` instead of `>>>` and excluded from "Targets in this chunk."

- [ ] **Step 3b: Manually verify the out-of-range chunk error**

`BathTime_dialogue` (660 lines) is confirmed multi-chunk at the default 50/10 settings. Find its guid and confirm the bounds check produces a clear error rather than a crash:
```bash
cd tools/annotate
python3 -c "
import json
convs = json.load(open('../../data/conversations.enGB.json'))
print(next(c['guid'] for c in convs if c.get('name') == 'BathTime_dialogue'))
"
python3 interactive_next.py --cache-dir /tmp/abelard_smoketest <paste the guid> 99
python3 interactive_next.py --cache-dir /tmp/abelard_smoketest <paste the same guid> -- -1
```
Expected: both print a one-line error on stderr naming the valid chunk range (e.g. "chunk 99 does not exist... valid range 0-N" / "chunk -1 does not exist..."), exit code 1 — not a Python traceback and not a silent, wrong success (Python's negative-index semantics would otherwise make `-1` quietly return the *last* chunk instead of erroring; the `--` before `-1` stops argparse from treating it as a flag).

- [ ] **Step 4: Clean up the smoke-test cache directory**

```bash
gio trash /tmp/abelard_smoketest /tmp/test_labels.json
```
(Per the operator's global CLAUDE.md rule against `rm`/`rm -rf` — not this project's own local `CLAUDE.md`, which only covers the humanizer skill for public writing — always `gio trash` for cleanup, never `rm`.)

- [ ] **Step 5: Commit**

```bash
git add tools/annotate/interactive_next.py
git commit -m "Add interactive_next.py: render the next unlabeled Abelard conversation or chunk"
```

---

## Plan self-review notes (for the record, not a task)

This plan went through two review passes before execution: a self-review after the first
draft, and an `advisor` review that caught two real bugs neither the self-review nor the
spec's own two review rounds had surfaced (both fixed inline above, not left as follow-up
work):

- **`interactive_submit.py`'s `run()` originally never checked the global already-labeled
  set** — only `interactive_next.py` did. A target already labeled via a different
  conversation would be shown as non-canonical (not required) by `interactive_next.py` but
  still *required* by `interactive_submit.py`, making that conversation permanently
  unsubmittable (`missing: <key>` forever). Fixed by giving `required_targets_for_chunk` an
  `already_labeled` parameter and having `run()` compute it via `scan_already_labeled_keys`
  — with the wrinkle that the scan must exclude the exact file this submission is about to
  overwrite, or resubmitting/correcting an already-labeled chunk sees its own prior output
  as an external conflict.
- **`abelard_targets()` originally didn't dedupe a text_key repeated *within one*
  conversation** (confirmed real on the actual corpus — `LucidIdira_dialogue` has this
  shape). `target_indices`'s dict-based lookup silently collapsed both occurrences to one
  index, and `validate_submission` would still iterate both as separate list entries,
  writing two records with the same `guid` into one cache file. Fixed by deduping inside
  `abelard_targets()` itself (first occurrence wins), which makes every downstream
  dict/set/zip keyed by `text_key` safe by construction rather than by caller discipline.

Both fixes are reflected directly in Task 1's and Task 3's code and tests above, not
described here as pending work.

A third review pass (Kimi, run manually against this repo — not from the plan's
descriptions, from actually executing code against the real files) found two more critical
findings and several minor ones, all verified independently before being fixed here:

- **`data/annotations/cache` — `annotate.py`'s own default — is not the full corpus.**
  Confirmed by direct count: 200 files / 5,599 guids, versus `data/annotations/cache_merged`'s
  1,328 files / 45,114 guids (an exact match with shipped `annotations.enGB.json`). Every
  merge command in this plan and the spec previously named `cache`, which would have wiped
  ~39,500 lines of production on the first real merge — the exact bug the repeatable
  `--cache-dir` fix (round 2) was meant to prevent, one level up, because both prior review
  rounds assumed the code's own comment ("the default cache dir already holds the full
  corpus") was true without checking the directory's actual contents. Fixed throughout Task
  2 and the spec; Task 2 Step 7 now re-verifies this fact directly rather than re-assuming it.
- **The `sorted()` fix (round 2) has a real, non-trivial effect on production, verified
  directly** (not assumed to be a no-op): a `sorted()` merge of `cache_merged` alone,
  followed by `reconcile_sarcasm_emotion` exactly as a real `--merge` does, changes 487 of
  the 45,114 shipped records (115 in `emotion`) versus today's production file — confirmed
  by actually running both the old (unsorted) and new (sorted) merge logic and diffing the
  results, twice, independently, with matching numbers both times. Task 2 Step 7 now
  produces this diff as a human-reviewable preview and explicitly does not run a real merge;
  `diff_cache_vs_production.py` was refactored to reuse `annotate.merge_cache_dirs` and
  accept multiple directories so that preview reflects exactly what a real merge would do.
- **Minor, also fixed:** a negative `--chunk`/explicit `chunk_index` argument to
  `interactive_next.py` silently rendered the *last* chunk instead of erroring (Python's
  negative-index semantics on `ranges[chunk_index]`) — now bounds-checked on both ends.
  `LucidIdira_dialogue`'s real intra-conversation duplicate `text_key` (positions 22 and 36)
  would have rendered as two separate `>>>` target markers for the same required label,
  even after the round-2 fix correctly deduped it in `abelard_targets()` — `render()` now
  tracks which target keys it has already marked and shows any repeat physical occurrence as
  plain dialogue instead. `interactive_next.py` hardcoded its displayed pace/nonverbal word
  lists instead of deriving them from `schema.PACES`/`schema.NONVERBALS` — a direct
  violation of this plan's own Global Constraints, now fixed to import and join them.
  Malformed submission JSON crashed with a raw traceback instead of a clean `SubmitError` —
  now caught and converted, with a test. A cleanup step's rationale cited "this project's
  `CLAUDE.md`" for the no-`rm` rule; that rule is actually in the operator's *global*
  `CLAUDE.md`, not this project's local one (which is only about the humanizer skill) —
  citation corrected.

A fourth pass (Kimi again, verifying the round-3 fixes specifically) confirmed everything
above was applied correctly, and found three residuals, all fixed and independently
re-verified before being committed:

- **Task 2 Step 7's expected preview number was simply wrong.** `diff_cache_vs_production.py`
  only ever compares the `emotion` field (never a full record) and never applies
  `reconcile_sarcasm_emotion` — so pointed at a raw `sorted()` merge it reports 312 emotion
  changes, not 487 (which was never a number that tool could produce at all, being an
  all-field count from a one-off comparison script written during spec review) or even 115
  (which only emerges once `reconcile_sarcasm_emotion` closes 197 of those 312 apparent
  gaps). Verified by actually running the numbers both ways. Rather than change
  `diff_cache_vs_production.py`'s own comparison semantics (out of scope — it's a
  general-purpose tool with its own use case), Step 7 now runs a small one-off snippet that
  reproduces exactly what a real `--merge` does (`merge_cache_dirs` + `reconcile_sarcasm_emotion`,
  diffing every field) — tested verbatim (with a temporary shim standing in for
  `merge_cache_dirs`, since Task 2's code doesn't exist yet at plan-review time) and
  confirmed it prints exactly "487 ... 115 ...".
- **`interactive_submit.py --chunk -1` wasn't bounds-checked** — only `interactive_next.py`
  was fixed for this in round 3. `required_targets_for_chunk` failed safe (an always-empty
  required set turns into a correct-but-confusing "unexpected guids" error) but didn't name
  the real problem. Now checks `chunk < 0` explicitly, with a test.
- **A non-dict per-record label value** (e.g. `{"a": "resigned"}` instead of
  `{"a": {"emotion": "resigned", ...}}`) crashed `validate_submission` with an
  `AttributeError` on `rec.get(...)` instead of the clean `SubmitError` the malformed-JSON
  fix (round 3) was supposed to guarantee. Now checked explicitly, with a test.

- **Spec coverage:** every function named in the spec's `context_window.py`/`interactive_next.py`/`interactive_submit.py` sections has a corresponding implementation and test above; the merge/diff `sorted()` fix, the repeatable `--cache-dir`, the dedup policy, and the canonical-chunk policy are all implemented, not just described.
- **Deliberate additions beyond the spec's literal function list:** `target_indices()` in `context_window.py` (the spec's `chunk_ranges`/`canonical_chunk` signatures take `list[int]` positions but nothing in the spec named the function that produces them from target *lines*); `scan_already_labeled_keys()` and the `already_labeled` parameter on `required_targets_for_chunk()` in `interactive_submit.py` (needed once the advisor review exposed that the dedup policy has to be enforced on the write path, not just the read/render path).
- **Type/signature consistency checked across tasks:** `chunk_ranges(lines, target_indices, chunk_size, overlap)` and `canonical_chunk(target_index, ranges)` are called with the same argument order and types in Task 1's tests, Task 3's `interactive_submit.py`, and Task 4's `interactive_next.py`. `required_targets_for_chunk`'s `(ranges, targets, idxs, chunk, already_labeled=frozenset())` signature matches between its Task 3 definition, its tests, and its two call sites in `run()`.
- **Not covered by this plan, deliberately (per spec's Non-goals):** the actual merge into `annotations.enGB.json` (a separate, explicit, human-triggered step after review), extending this to the other 25 speakers, and voiced-catalog-clip relabeling.
