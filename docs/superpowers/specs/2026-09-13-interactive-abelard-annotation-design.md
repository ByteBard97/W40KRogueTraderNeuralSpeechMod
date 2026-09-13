# Interactive (Claude-in-the-loop) annotation harness for Abelard's unvoiced lines

Status: approved for implementation
Date: 2026-09-13

## Problem

Abelard has 575 unvoiced dialogue lines (across 240 conversations in
`data/conversations.enGB.json`) that need an emotion/pace/delivery annotation for
expressive TTS. The existing automated pass (`tools/annotate/annotate.py --speaker Abelard
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
- Not re-implementing schema validation, merge, or diff review — `tools/annotate/schema.py`,
  `annotate.py --merge`, and `diff_cache_vs_production.py` already do this and are reused
  unchanged (see "Downstream reuse").
- Not handling any speaker other than Abelard, or voiced-catalog-clip relabeling (curate.html)
  — both explicitly deferred to a later pass, per user decision during brainstorming.
- Not auto-merging into `annotations.enGB.json`. Merge is a separate, explicit,
  human-triggered step, same as the existing gpt-oss pilot workflow.

## Data reference (verified against the actual files, not assumed)

- `data/conversations.enGB.json`: a list of 1329 conversation objects, each with a `lines`
  list already in natural (depth-first) reading order. Each line has `guid`, `kind`
  (`cue`/`answer`/`answers_list`/...), `parent`, `via`, `depth`, `text_key`, `text`,
  `voiced` (null = unvoiced), `speaker` (`{"kind": "player"}` /
  `{"kind": "default_speaker"}` / `{"kind": "unit", "name": "Abelard", ...}`), `animation`.
  Median conversation length is 31 lines; a few outliers run past 1000 — the fixed-window
  design (below) means conversation length no longer needs special-casing.
- Abelard has 660 total lines / 575 unvoiced, across 240 conversations.
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
a small `context_window.py` helper module for the windowing/merging logic (kept separate so
it's independently unit-testable).

### `tools/annotate/context_window.py` (new, pure logic, no I/O)

```python
def abelard_targets(conv: dict) -> list[dict]:
    """Return conv['lines'] entries where speaker name == 'Abelard' and voiced is None
    and text/text_key are present, in document order."""

def build_windows(lines: list[dict], target_indices: list[int],
                   before: int = 3, after: int = 2) -> list[tuple[int, int]]:
    """For each target index, compute [i-before, i+after] clamped to bounds, then merge
    any windows that overlap or touch into a single (start, end) span. Returns spans in
    document order."""
```

- `before=3, after=2` are the defaults agreed with the user; kept as parameters (not
  constants) so `--context full` can call the same function with `before=len(lines),
  after=len(lines)` to get the whole conversation instead of a special-cased code path.
- Windows are computed over the *conversation's full line list* (all speakers), never the
  speaker-filtered list — this is the actual fix for the root cause. Only lines with both
  `text` and `text_key` participate in indices/windows (structural nodes like
  `answers_list` have neither and are skipped, matching `conv_payload()`'s existing filter).

### `tools/annotate/interactive_next.py` (new)

```
usage: interactive_next.py [--cache-dir DIR] [conv_guid] [--context full]
```

- No `conv_guid`: scans `data/conversations.enGB.json` in order, finds the first
  conversation with at least one Abelard-unvoiced line whose `text_key` is *not* already
  present in any `*.json` file under `--cache-dir` (default
  `data/annotations/cache_claude_abelard/`), and renders it.
- `conv_guid` given: re-renders that specific conversation (for revisits/expansion),
  regardless of cache state.
- `--context full`: uses the whole-conversation window instead of the default 3/2 window.
- Output format (plain text to stdout, meant to be read directly, not parsed):
  ```
  Conversation: <name> (<guid>)
  Abelard — <full bio paragraph from character_bios.json["Abelard"], printed as-is>
  Vocabulary: resigned, hopeful, defiant, resolute, skeptical, sad, firm, pleading, stern,
              cautious, mournful, neutral, dramatic, relieved, sarcastic, accusatory, angry,
              desperate, fear, indignant, surprised
  Paces: slow, normal, fast | Nonverbal (optional): laugh, chuckle, sigh, gasp, groan, sniff,
         cough, clear_throat, shush

  --- (lines 12-19 of 31; gap before/after not shown) ---
  [player] "How is Ulfar? Has he regained consciousness?"
  >>> [be54d24e-...] Abelard: "He is feeling better, Lord Captain..."
  [default_speaker] "Good. Send my regards when he wakes."
  ...

  Targets in this conversation: be54d24e-... , <guid2>, ...
  Submit with: interactive_submit.py <conv_guid> <json-file>
  ```
  A `--- gap ---` marker separates non-adjacent merged spans so it's visually clear the
  window skipped material, matching how a human would expect a script excerpt to read.
- Exits with a clear "nothing left to label" message (and exit code 0) once every Abelard
  unvoiced line across all 240 conversations has a corresponding cache entry.

### `tools/annotate/interactive_submit.py` (new)

```
usage: interactive_submit.py [--cache-dir DIR] <conv_guid> <json_file_or_->
```

Input JSON shape (what Claude writes): a plain dict `{guid: {emotion, intensity, pace,
nonverbal, instruct}}` for every Abelard target in that conversation — dict-keyed by guid
for easy hand-authoring, converted internally to the `lines` list format on write.

Validation, in order, each a hard failure (nonzero exit, nothing written, exact reason
printed):
1. Look up the conversation by `conv_guid` in `conversations.enGB.json`; compute its actual
   Abelard-unvoiced target guid set via `abelard_targets()`.
2. Submitted guid set must equal the target set exactly (report missing / unexpected guids
   by name, not just a count).
3. Each record validated against `schema.build_json_schema(speaker_vocab["Abelard"]["words"])`
   — reuses the exact enum Claude was shown, so a typo'd emotion is caught immediately.
4. `pace` must be one of `schema.PACES`; `nonverbal` entries must all be in
   `schema.NONVERBALS`; `intensity` clamped-checked to `[0, 1]` (out of range is a hard
   error here, not silently clamped, since this is human-authored, not model output that
   needs defensive clamping).
5. `instruct` non-empty, ≤300 chars (matches the schema's existing `maxLength`).

On success: computes `text_hash = sha1(text)[:12]` for each line (matching
`annotate.py.line_hash()` exactly), writes
`<cache_dir>/<conv_guid>.json` as `{"conv": conv_guid, "model": "claude-interactive",
"lines": [...]}`, and prints a one-line confirmation with remaining-conversation count.

### Downstream reuse (unchanged, no new code)

- Review: `python3 tools/annotate/diff_cache_vs_production.py data/annotations/cache_claude_abelard --out <report>.md`
- Merge (only when the user says so):
  `python3 tools/annotate/annotate.py --merge --cache-dir data/annotations/cache_claude_abelard`
  This also runs `reconcile_sarcasm_emotion` — tuned for qwen3's failure mode. Since Claude's
  `instruct` text is free-form, there's a small chance it could false-trigger this heuristic
  (e.g. writing "sarcastic dig" in `instruct` while intentionally choosing a different
  emotion). Not fixed by this spec; flagged for the diff-review step to catch, same as any
  other merge concern.

## Data flow

```
conversations.enGB.json ─┬─> interactive_next.py ──(prints script excerpt)──> Claude reads
                          │                                                        │
                          │                                                  decides labels
                          │                                                        │
speaker_vocab.json ───────┘                                                        v
                                                                          interactive_submit.py
                                                                                    │
                                                                                    v
                                                          data/annotations/cache_claude_abelard/<guid>.json
                                                                                    │
                                                              (explicit, later, human-triggered)
                                                                                    v
                                                    annotate.py --merge  ──>  annotations.enGB.json
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

## Testing

`tools/annotate/tests/test_context_window.py` (new, matches existing test style):
- `abelard_targets()`: finds the right lines given a synthetic conversation with mixed
  speakers, voiced/unvoiced, and a couple of structural (`answers_list`) nodes with no text.
- `build_windows()`: single target in the middle of a long line list produces the expected
  `before=3/after=2` bounds; two targets close together merge into one span; a target near
  the start/end clamps rather than going out of bounds; `--context full` equivalent
  (`before/after` >= line count) collapses to the whole conversation as one span.

`tools/annotate/tests/test_interactive_submit.py` (new):
- Happy path: valid submission for a small fixture conversation writes the expected cache
  file content exactly (including `text_hash`).
- Rejects: missing guid, extra/unexpected guid, emotion not in Abelard's vocab, invalid
  pace, invalid nonverbal entry, out-of-range intensity, empty `instruct` — each its own
  test, each asserting nothing was written to the cache dir.

No new tests needed for `interactive_next.py`'s stdout rendering — it's cheap enough to spot
check visually (as the actual harness usage does anyway); its scan/skip logic is exercised
transitively by `test_context_window.py`.

## Rollout / iteration

Claude runs `interactive_next.py` → reads → `interactive_submit.py` → repeat, once per
conversation, 240 times total. This spans many conversation turns and is not expected to
finish in one sitting. Nothing touches production `annotations.enGB.json` until the user
reviews the diff report and explicitly runs the merge step.
