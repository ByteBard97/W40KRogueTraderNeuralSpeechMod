# Interactive (Claude-in-the-loop) annotation harness for Abelard's unvoiced lines

Status: approved for implementation
Date: 2026-09-13

## Problem

Abelard has 572 unvoiced dialogue lines with real text (across 219 conversations in
`data/conversations.enGB.json` — see "Data reference" below for how this number relates to
the other, larger counts for "lines involving Abelard") that need an emotion/pace/delivery
annotation for expressive TTS. The existing automated pass (`tools/annotate/annotate.py --speaker Abelard
--unvoiced-only`, backed by qwen3/gpt-oss via Ollama) produces low-quality labels. Root
cause: `conv_payload()` filters a conversation down to *only* the target speaker's lines
before sending it to the model, so the model annotating Abelard's lines never sees what he's
responding to.

The fix is not a better model or prompt — it's a human (here, Claude, in this conversation)
doing the labeling directly, with real conversational context. This spec covers a small
harness that lets that happen iteratively, conversation by conversation, without touching
production data until a human explicitly merges it.

## Non-goals

- Not building an MCP server. Claude already has Bash/Read/Write; a script pair invoked via
  Bash gives the same interactivity with none of the protocol/registration overhead.
- Not re-implementing schema validation or diff review — `tools/annotate/schema.py` and
  `diff_cache_vs_production.py` are reused unchanged. `annotate.py --merge` needs one small,
  backward-compatible fix (see "Downstream reuse: the merge bug") — everything else about it
  is reused as-is.
- Not handling any speaker other than Abelard, or voiced-catalog-clip relabeling (curate.html)
  — both explicitly deferred to a later pass, per user decision during brainstorming.
- Not auto-merging into `annotations.enGB.json`. Merge is a separate, explicit,
  human-triggered step, same as the existing gpt-oss pilot workflow.

## Data reference (verified against the actual files, not assumed)

- `data/conversations.enGB.json`: a list of 1329 conversation objects, each with a `lines`
  list already in natural (depth-first) reading order. Each line has `guid`, `kind`
  (`cue`/`answer`/`answers_list`/...), `parent`, `via`, `depth`, `text_key`, `text`,
  `voiced` (absent or null = unvoiced — 24,221 lines corpus-wide, including 2 of Abelard's,
  omit the key entirely rather than setting it null; `l.get("voiced") is None` treats both
  the same, matching `conv_payload()`), `speaker` (`{"kind": "player"}` /
  `{"kind": "default_speaker"}` / `{"kind": "unit", "name": "Abelard", ...}` / the `speaker`
  key absent entirely — 23,689 lines corpus-wide have no `speaker` key at all), `animation`.
  Median conversation length overall is 31 lines; among the subset that actually contain an
  Abelard unvoiced target it's 65, with outliers up to 660 — see "Tuning" below for how
  conversation length is handled. Renderer note: a line with no `speaker` key needs the same
  fallback `conv_payload()` already uses (`sp.get("name") or sp.get("kind") or "unknown"`),
  not a crash on `None.get(...)`.
- Three different, easily-confused counts for "how much of Abelard is in scope," all
  verified exactly against the actual data — the spec uses the last one as its working
  number and never the other two:
  - **240** conversations contain *any* Abelard line (voiced or not).
  - **221** of those conversations contain at least one *unvoiced* Abelard line
    (`speaker.name == "Abelard" and voiced is None`, 575 lines total).
  - **219** conversations remain once also requiring `text` and `text_key` to be present
    (what `abelard_targets()` actually checks), covering **572** target lines — this is the
    number `interactive_next.py` iterates over, and the number the earlier pilot handoff
    presumably meant by "572." The exact number is filter-defined and must never be
    hardcoded into code or tests; `abelard_targets()` is the single source of truth for it.
- **Duplicate `text_key`s among the 572 targets, verified**: 13 of the 572 target lines
  share a `text_key` with another target line, 6 of those 13 across *different*
  conversations (e.g. `AlternativeLordCaptains_dialogue` and
  `AlternativeLordCaptains_Fem_dialogue` share three keys; `LucidIdira_dialogue` has an
  internal duplicate). None of the 13 have conflicting `text`, so treating a `text_key` as
  needing exactly one label — not one per occurrence — is safe. See "Deduplication and
  canonical-chunk policy" below; this is the single most important correctness fix from
  spec review round 2.
- `data/character_bios.json["Abelard"]`: one paragraph of character voice/personality
  description, used as a reminder header in the harness output.
- `data/voices/emotion_banks/speaker_vocab.json["Abelard"]["words"]`: his 21-word emotion
  vocabulary (derived from Ultravox cross-mode agreement on his official voiced lines) —
  this is the enum the harness validates against, not the generic 12-word `schema.EMOTIONS`.
- `tools/annotate/schema.py`: `build_json_schema(emotions)`, `PACES = ["slow","normal","fast"]`,
  `NONVERBALS = [...]` — reused directly for validation.
- Existing cache file shape (what `annotate.py` writes per conversation, and what `--merge`
  and `diff_cache_vs_production.py` both consume):
  ```json
  {"conv": "<conv_guid>", "model": "<string>",
   "lines": [{"guid": "<text_key>", "emotion": "...", "intensity": 0.0-1.0,
              "pace": "slow|normal|fast", "nonverbal": [...], "instruct": "...",
              "text_hash": "<sha1(text)[:12]>"}, ...]}
  ```
  Note `guid` here is the line's `text_key`, not the conversation-tree `guid` — matches
  `conv_payload()`'s existing convention.

## Architecture

Two new scripts in `tools/annotate/`, both importing `schema.py` for validation and sharing
a small `context_window.py` helper module for the target-finding/chunking logic (kept
separate so it's independently unit-testable).

### `tools/annotate/context_window.py` (new, pure logic, no I/O)

Two earlier designs were tried and dropped during spec review:
1. Flat-array index slicing (`lines[i-3:i+2]`) — rejected because in a branching dialogue
   tree, the lines immediately before/after a target's array position can belong to a
   different, untaken sibling branch: plausible-looking but wrong context.
2. A `parent`-pointer tree walk (ancestors/descendants) to fix that — dropped after
   checking it against the largest *relevant* conversation, `BathTime_dialogue` (660 lines,
   16 Abelard targets): it's a long, mostly linear thread with no clean branch structure to
   exploit (grouping by depth-1 branch produced one 657-line group and two trivial ones), so
   the tree walk bought accuracy the data doesn't actually have while adding real
   implementation complexity. (An earlier draft of this reasoning cited a different
   1363-line conversation, `Epilogue_dialogue` — that conversation contains zero Abelard
   lines at all and was never actually a candidate the harness would process; corrected
   during spec review round 2. The conclusion itself holds on the real data.)

Final design, per direct user steer: show the **whole conversation** (every speaker, every
line, real document order — this is what actually fixes the root cause) for the common
case, and fall back to flat, tunable chunking only for the minority of conversations too
long to read in one pass. 219 conversations contain an Abelard target; median length among
them is 65 lines, but 36 exceed 150 (max 660, confirmed independently by two review
passes). No hardcoded chunk size is assumed to be right — see "Tuning" below.

```python
def abelard_targets(conv: dict) -> list[dict]:
    """Return conv['lines'] entries where speaker name == 'Abelard' and voiced is None
    and text/text_key are present, in document order. This is the single source of truth
    for "how many lines need labeling" - never hardcode a count derived from it."""

def dialogue_lines(conv: dict) -> list[dict]:
    """All lines in the conversation with real text and text_key (all speakers), in
    document order - the actual content rendered for 'show the whole conversation'."""

def chunk_ranges(lines: list[dict], target_indices: list[int],
                  chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    """If len(lines) <= chunk_size: a single (0, len(lines)) range - the whole thing, no
    chunking. Otherwise split into fixed-size (start, end) ranges of chunk_size lines with
    `overlap` lines shared between consecutive ranges, then drop any range that contains
    none of target_indices. Ranges returned in document order."""

def canonical_chunk(target_index: int, ranges: list[tuple[int, int]]) -> int:
    """Index into `ranges` of the first (lowest-index) range containing target_index - the
    one chunk that requires/accepts a submitted label for this target. Any other range
    containing it still renders it, but as already-labeled-elsewhere, not as a submission
    requirement (see 'Deduplication and canonical-chunk policy')."""

def unlabeled_targets(targets: list[dict], already_labeled_keys: set[str]) -> list[dict]:
    """targets minus any whose text_key is in already_labeled_keys. Pure function - the
    caller (interactive_next.py) does the actual cache-dir scan and passes the resulting
    set in, keeping this module free of file I/O. See 'Deduplication and canonical-chunk
    policy' for why a text_key can legitimately need this (13 targets share a text_key with
    another target, 6 of those across different conversations)."""
```

- `chunk_size` doubles as the whole-conversation threshold: anything at or under it is
  shown in full, nothing dropped.
- Rendering (in `interactive_next.py`) resolves each Abelard target within its chunk's
  range and marks it inline (`>>> [guid] Abelard: ...`) among every other speaker's lines
  in that range — no merging/gap logic needed since a chunk is already one contiguous run.

### Deduplication and canonical-chunk policy (added in spec review round 2)

Two real correctness gaps were found by re-checking the design against actual simulated
output, not just against the doc's own internal logic — both are the same underlying
problem (a `text_key` submitted more than once, landing in two different cache files, whose
merge winner is then arbitrary) with two different causes:

1. **Cross-conversation duplicates** (13 target `text_key`s, 6 cross-conversation — see
   "Data reference" above). **Policy: label once, globally, first-seen wins for *scanning*
   purposes.** `interactive_next.py` tracks every `text_key` already present in *any*
   existing cache file in `--cache-dir` (regardless of which conversation's file it's in),
   and excludes already-covered `text_key`s from a conversation's required target set before
   computing chunks or reporting "targets in this chunk." If Abelard's line already got a
   label while working through an earlier conversation, a later conversation that happens to
   reuse the same line (e.g. `AlternativeLordCaptains_dialogue` /
   `AlternativeLordCaptains_Fem_dialogue`) doesn't ask for it again.
2. **Chunk-overlap double-coverage** (empirically simulated at the default 50/10 settings
   across all 219 conversations: 0 targets dropped, ~60 target *occurrences* land in the
   overlap zone shared by two consecutive chunks — confirmed independently by two review
   passes with close but not identical counts, the exact number being a chunking-detail
   artifact, not something to hardcode). **Policy: each target has exactly one *canonical*
   chunk — the first chunk (lowest index) whose range contains it.** Only the canonical
   chunk's required-target-set (and `interactive_submit.py`'s validation) includes it. A
   later chunk that also contains the same line in its range still *renders* it (for reading
   continuity across the overlap — you can see how the scene continues) but marks it as
   already-labeled-elsewhere rather than as `>>>` requiring a submission
   (e.g. `··· [guid] Abelard (labeled in chunk 1): "..."`).

Both policies are enforced in `context_window.py` so they're covered by the same unit tests
as `chunk_ranges()`, not left as an `interactive_next.py`/`interactive_submit.py`
implementation detail that could drift between the two scripts.

### Tuning `chunk_size` / `overlap`

Both are CLI flags on `interactive_next.py` (see below), not constants, and deliberately
start conservative: `--chunk-size 50 --chunk-overlap 10` as the initial defaults. Per user
direction, this is meant to be tuned empirically once real labeling starts — if 50-line
chunks turn out comfortable, raise `--chunk-size` (fewer, larger chunks, less redundant
re-reading of overlap regions across chunks of the same big conversation); if even 50 lines
of a dense scene is hard to hold in context alongside its bio/vocabulary header, lower it.
No code change needed to retune, only the flag value.

**Retuning mid-corpus is safe by construction**: `chunk_size`/`chunk_overlap` are recorded
in every cache file written for a chunked conversation (extra `"chunk_size"`,
`"chunk_overlap"` keys alongside the existing `"conv"`/`"model"`/`"lines"`). Both scripts,
before computing `chunk_ranges(...)` for a given `conv_guid`, check whether *any*
`<cache_dir>/<conv_guid>__chunk*.json` already exists; if so, they reuse that
conversation's recorded values instead of the current CLI flags, so a later `--chunk-size`
change only affects conversations not yet started. A conversation that fit in a single,
unchunked cache file (no `chunk_size` recorded, because it never needed chunking) is
unaffected by this regardless of chunk-size changes, since `chunk_ranges` always returns
one whole-conversation range when `len(lines) <= chunk_size`.

### `tools/annotate/interactive_next.py` (new)

```
usage: interactive_next.py [--cache-dir DIR] [--chunk-size N] [--chunk-overlap N]
                            [conv_guid [chunk_index]]
```

- No arguments: reads every `*.json` file already in `--cache-dir` once to build the
  global `already_labeled_keys` set (every `text_key` that has a label anywhere, in any
  conversation's cache file). Then scans `data/conversations.enGB.json` in order; for each
  conversation with at least one target in `unlabeled_targets(abelard_targets(conv),
  already_labeled_keys)`, computes `chunk_ranges(...)` over those remaining targets and
  finds the first (conversation, chunk) pair not yet covered by a cache file (see naming
  below), and renders it.
- `conv_guid` (and optional `chunk_index`, default 0): re-renders that specific
  conversation/chunk (for revisits), regardless of cache state.
- Cache file naming: `<cache_dir>/<conv_guid>.json` when the conversation fit in one chunk
  (the common case — no filename change from the original design), or
  `<cache_dir>/<conv_guid>__chunk<N>.json` per chunk otherwise. `interactive_next.py`'s scan
  checks for whichever name applies to that conversation's actual chunk count.
- Output format (plain text to stdout, meant to be read directly, not parsed):
  ```
  Conversation: <name> (<guid>) — chunk 1/1 (17 lines)
  Abelard — <full bio paragraph from character_bios.json["Abelard"], printed as-is>
  Vocabulary: resigned, hopeful, defiant, resolute, skeptical, sad, firm, pleading, stern,
              cautious, mournful, neutral, dramatic, relieved, sarcastic, accusatory, angry,
              desperate, fear, indignant, surprised
  Paces: slow, normal, fast | Nonverbal (optional): laugh, chuckle, sigh, gasp, groan, sniff,
         cough, clear_throat, shush

  [player] "How is Ulfar? Has he regained consciousness?"
  >>> [be54d24e-...] Abelard: "He is feeling better, Lord Captain..."
  [default_speaker] "Good. Send my regards when he wakes."
  ··· [a1b2c3d4-...] Abelard (labeled in chunk 1): "..."
  ...

  Targets in this chunk: be54d24e-... , <guid2>, ...
  (already labeled elsewhere, shown for context only: a1b2c3d4-...)
  Submit with: interactive_submit.py <conv_guid> [--chunk N] <json-file>
  ```
  When a conversation is chunked, the header shows `chunk 2/5 (52 lines, overlap 10)` etc.,
  so it's obvious a neighboring chunk exists if a line's context still feels incomplete —
  rerunning with a larger `--chunk-size` for just that conversation is the manual escape
  hatch, no separate "expand" flag needed now that chunking is purely size-driven.
- Exits with a clear "nothing left to label" message (and exit code 0) once
  `already_labeled_keys` covers every `text_key` returned by `abelard_targets()` across all
  219 relevant conversations.

### `tools/annotate/interactive_submit.py` (new)

```
usage: interactive_submit.py [--cache-dir DIR] [--chunk N] <conv_guid> <json_file_or_->
```

Input JSON shape (what Claude writes): a plain dict `{guid: {emotion, intensity, pace,
nonverbal, instruct}}` for every Abelard target *in that chunk* — dict-keyed by guid for
easy hand-authoring, converted internally to the `lines` list format on write.

Validation, in order, each a hard failure (nonzero exit, nothing written, exact reason
printed):
1. Look up the conversation by `conv_guid` in `conversations.enGB.json`; recompute
   `chunk_ranges(...)` with the same `--chunk-size`/`--chunk-overlap` recorded for this
   conversation (or the current flags, if it's not chunked yet); take only the targets
   whose `canonical_chunk(...)` equals `--chunk` (default 0) — a target merely *rendered*
   in this chunk via overlap, but canonical to an earlier chunk, is not required here.
2. Submitted guid set must equal that chunk's *canonical* target set exactly (report
   missing / unexpected guids by name, not just a count).
3. Each record's `emotion` must be a member of `speaker_vocab["Abelard"]["words"]` — a
   plain `in` check against the same list Claude was shown, so a typo'd emotion is caught
   immediately. (Not run through `schema.build_json_schema(...)`/a `jsonschema` validator:
   nothing in `tools/annotate/` depends on the `jsonschema` package today — that function
   only ever builds a dict for Ollama's constrained-decoding parameter — and adding that
   dependency for one enum check is unwarranted when steps 4-5 already hand-roll everything
   else.)
4. `pace` must be one of `schema.PACES`; `nonverbal` entries must all be in
   `schema.NONVERBALS`; `intensity` clamped-checked to `[0, 1]` (out of range is a hard
   error here, not silently clamped, since this is human-authored, not model output that
   needs defensive clamping).
5. `instruct` non-empty, ≤300 chars (matches the schema's existing `maxLength`).

On success: computes `text_hash = sha1(text)[:12]` for each line (matching
`annotate.py.line_hash()` exactly), writes `<cache_dir>/<conv_guid>.json` (unchunked) or
`<cache_dir>/<conv_guid>__chunk<N>.json` (chunked) as `{"conv": conv_guid, "model":
"claude-interactive", "lines": [...]}`, plus `"chunk_size"`/`"chunk_overlap"` keys when
chunked (see "Retuning mid-corpus is safe by construction" above), and prints a one-line
confirmation with remaining-conversation count.

### Downstream reuse: review (unchanged) and merge (one required fix)

- Review, reused with the same `sorted()` fix as merge (not otherwise changed):
  `python3 tools/annotate/diff_cache_vs_production.py data/annotations/cache_claude_abelard
  --out <report>.md`. Verified safe against a small cache: it iterates `for g in pilot`
  (`diff_cache_vs_production.py:33-36`), never the other direction, so a 572-entry cache
  diffed against the 45,114-entry production file does not produce spurious "removed" rows
  for everything absent from the small cache — 557 of the 572 targets already exist in
  production, so the report is mostly changed/unchanged rows plus ~15 new ones, exactly
  what the tool is shaped for. Its `load_cache()` (line 20) has the same unsorted-glob
  collision-ordering gap as `--merge`'s loop, for the same pre-existing reason (1685
  corpus-wide duplicate keys); fixed identically since it's the same root cause.

- **Merge bug found during spec review, must be fixed as part of this work, not deferred**:
  `annotate.py --merge` (`annotate.py:247-257`) does not update production — it *rebuilds*
  `annotations.enGB.json` from scratch out of nothing but `--cache-dir`'s contents (`merged =
  {}`, then only ever populated from files under that one directory). The existing workflow
  only looks additive because its default cache dir already holds the full corpus. Pointed
  at `data/annotations/cache_claude_abelard` alone, it would overwrite the 45,114-line
  production file with just Abelard's ~572 entries — silent, severe data loss.

  Fix: make `--cache-dir` repeatable (`action="append"`, default `[CACHE]` preserving
  today's single-dir behavior exactly) and change the merge loop to glob each directory,
  **sorted**, in the order given, with a later directory's entry for a given guid
  overriding an earlier one. Merging Claude's work in then looks like:
  ```
  python3 tools/annotate/annotate.py --merge \
      --cache-dir data/annotations/cache --cache-dir data/annotations/cache_claude_abelard
  ```
  i.e. "full corpus, with Abelard's interactive labels taking precedence where they exist."

  The `sorted()` is a second fix bundled into the same code, found during spec review round
  2: `cache_dir.glob("*.json")` iterates in arbitrary filesystem (`os.scandir`) order, and
  the production cache directory already has 1685 corpus-wide duplicate `text_key`s across
  its per-conversation files today — meaning **today's merge already silently picks an
  arbitrary winner** for those, nondeterministically across machines/runs. This isn't
  something the interactive harness introduces; it's a pre-existing gap in code this spec
  is already modifying, cheap to close while there, and worth fixing now rather than
  rediscovering later. Consequence for the "byte-identical" backward-compat claim: a single
  `--cache-dir` run is byte-identical to *a resort of* today's output, not necessarily
  today's literal historical output if that output happened to depend on scandir order for
  one of those 1685 collisions — the compat test (below) must pin expected output against a
  freshly-computed `sorted()` merge, not a captured historical artifact.

  A second, separate consumer of `--cache-dir` needs a decision now that it's a list: the
  non-merge (annotation-run) path (`annotate.py:226-227` for the `mkdir`, `:270-277` for
  per-conversation cache writes) currently assumes one directory. **Decision: the
  annotation-run path writes to `cache_dirs[-1]`** (the last directory given) — with today's
  single-value usage unchanged (`[-1]` of a one-element list is that element), and no
  present use case for running an automated annotation pass with multiple `--cache-dir`
  values, so this is a forward-compatible default rather than a real design tradeoff.

  This is the one piece of "reuse" that requires an actual (small, backward-compatible)
  code change to `annotate.py`, not zero new code.

  `--merge` also runs `reconcile_sarcasm_emotion` — tuned for qwen3's specific failure mode
  of picking an emotion enum that contradicts its own free-text `instruct`. Claude's
  `instruct` text is free-form and could in principle false-trigger it (e.g. writing
  "a sarcastic dig" while intentionally choosing a different emotion for good reason). Not
  fixed by this spec; the diff-review step is what's expected to catch it, same as any other
  merge concern, human-authored or not.

  One more thing to note in that same review pass, not a bug to fix here: Abelard's
  21-word per-speaker vocabulary includes words outside the generic 12-word
  `schema.EMOTIONS` (e.g. `resigned`, `stern`, `indignant`, `accusatory`, `mournful`).
  Whether the downstream TTS-engine emotion translators handle those words is a pre-existing
  question from the per-speaker-vocab decision, not something this harness creates — it's
  part of why the gpt-oss pilot is still unmerged, and belongs in the same merge conversation.

## Data flow

```
conversations.enGB.json ─┬─> interactive_next.py ──(prints conversation or chunk)──> Claude reads
                          │                                                              │
                          │                                                        decides labels
                          │                                                              │
speaker_vocab.json ───────┘                                                              v
                                                                                interactive_submit.py
                                                                                          │
                                                                                          v
                                            data/annotations/cache_claude_abelard/<conv_guid>[__chunkN].json
                                                                                    │
                                                              (explicit, later, human-triggered)
                                                                                    v
                                    annotate.py --merge --cache-dir cache --cache-dir cache_claude_abelard
                                                                                    │
                                                                                    v
                                                                       annotations.enGB.json
```

## Error handling

- `interactive_next.py` with a bad `--cache-dir` (doesn't exist): creates it (matches
  `annotate.py`'s existing `mkdir(parents=True, exist_ok=True)` behavior) rather than
  erroring, since an empty cache dir is just "nothing labeled yet."
  `interactive_submit.py` with a bad `--cache-dir`: same.
- `interactive_submit.py` never partially writes — validate everything in memory first,
  write the file only after all checks pass.
- A conversation with zero Abelard-unvoiced lines is simply never surfaced by
  `interactive_next.py` — not an error case, just filtered out during the scan.
- A `--chunk` value with no corresponding range (e.g. stale index after the conversation's
  recorded `chunk_size` produced fewer chunks than expected) is a hard error naming the
  valid chunk count, not a silent no-op.
- `--chunk-overlap >= --chunk-size` is rejected at CLI parse time in both scripts (found
  during spec review round 2): `chunk_ranges()`'s advance-by-`chunk_size - overlap` step
  would be zero or negative, looping forever instead of erroring.

## Testing

`tools/annotate/tests/test_context_window.py` (new, matches existing test style):
- `abelard_targets()`: finds the right lines given a synthetic conversation with mixed
  speakers, voiced/unvoiced, a couple of structural (`answers_list`) nodes with no text, and
  a line with no `speaker` key at all (must not crash, must be excluded since it can't be
  Abelard).
- `dialogue_lines()`: includes all speakers, excludes textless structural nodes.
- `chunk_ranges()`: a conversation at/under `chunk_size` returns one whole-conversation
  range; one well over it splits into multiple ranges with the requested overlap; a range
  containing no Abelard target is dropped; a target exactly on a chunk boundary lands in at
  least one retained range (never silently lost between two ranges) — this was verified
  empirically against all 219 real conversations during spec review (zero dropped at the
  default 50/10 settings) and should be exercised as a property, not just a hand-picked
  example.
- `canonical_chunk()`: a target appearing in only one range returns that range's index; a
  target in the overlap of two consecutive ranges returns the lower (earlier) index.
- `unlabeled_targets()`: targets whose `text_key` is in `already_labeled_keys` are excluded;
  others pass through unchanged; an empty `already_labeled_keys` is a no-op.

`tools/annotate/tests/test_interactive_submit.py` (new):
- Happy path: valid submission for a small, unchunked fixture conversation writes the
  expected cache file content exactly (including `text_hash`).
- Happy path, chunked: a fixture conversation long enough to produce 2+ chunks writes
  `<conv_guid>__chunk1.json` for `--chunk 1`, with `chunk_size`/`chunk_overlap` recorded in
  the file; a second `interactive_next.py` call on the same conversation with a different
  `--chunk-size` reuses the recorded value rather than the new flag.
- Rejects: missing guid, extra/unexpected guid, emotion not in Abelard's vocab, invalid
  pace, invalid nonverbal entry, out-of-range intensity, empty `instruct` — each its own
  test, each asserting nothing was written to the cache dir.
- Canonical-chunk enforcement: submitting a guid whose canonical chunk is a *different*
  chunk than `--chunk` is rejected as an unexpected guid, even though that guid is rendered
  in this chunk too (via overlap).
- `--chunk-overlap >= --chunk-size` is rejected before any file is read.

`tools/annotate/tests/test_annotate.py` (existing file, extended):
- `--merge` with two `--cache-dir` values: a guid present in both takes the later
  directory's version; a guid present in only one directory passes through unchanged; a
  single `--cache-dir` (today's only supported form) still produces output identical to a
  freshly-computed `sorted()`-order merge (not a captured pre-change artifact, since that
  artifact could itself depend on undefined scandir order for one of the 1685 corpus-wide
  duplicate keys).
- Merge is deterministic across two runs with cache files re-created in a different
  filesystem order (regression test for the `sorted()` fix).

No new tests needed for `interactive_next.py`'s stdout rendering — it's cheap enough to spot
check visually (as the actual harness usage does anyway); its scan/skip logic is exercised
transitively by `test_context_window.py`.

## Rollout / iteration

Claude runs `interactive_next.py` → reads the whole conversation (or chunk) → decides
labels → `interactive_submit.py` → repeat, once per (conversation, chunk) pair — 219
conversations, the large majority single-chunk, a minority (36 over 150 lines) split into
more than one chunk at the starting `--chunk-size 50`. The global dedup policy means a
handful of the 572 target lines (13, 6 cross-conversation) only need labeling once despite
appearing as a target more than once, so the real number of distinct labeling decisions is
slightly under 572. This spans many conversation turns and is not expected to finish in one
sitting. Nothing touches production `annotations.enGB.json` until the user reviews the diff
report and explicitly runs the two-`--cache-dir` merge.

Start small and tune: label a handful of conversations first, confirm the chunk size feels
right (comfortable to read and label accurately, not so small that scenes feel choppy or so
large that quality drops), adjust `--chunk-size`/`--chunk-overlap` if needed, then continue
through the rest.
