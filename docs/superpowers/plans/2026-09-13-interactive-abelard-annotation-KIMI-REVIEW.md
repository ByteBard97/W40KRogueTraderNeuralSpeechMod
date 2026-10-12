# Kimi review of the implementation plan: interactive Abelard annotation harness

Reviewed: `docs/superpowers/plans/2026-09-13-interactive-abelard-annotation.md` at commit
`dc4a38e`, against the live repo (code, corpus, and cache dirs), on 2026-09-13. Every
finding below was verified by running code against the real data, not by reading the plan's
descriptions of it.

**Verdict: the plan's core design is sound and its two headline dedup fixes genuinely work
— but it has one critical factual error that recreates the exact production-data-loss bug
the merge fix was meant to prevent, one level up. Do not execute Task 2's verification
step or any merge until Finding 1 is fixed in the plan text.**

## Critical findings

### 1. The documented merge uses the wrong base cache directory — it would wipe ~39,500 production lines

The spec and plan both document the merge as:

```
annotate.py --merge --cache-dir data/annotations/cache --cache-dir data/annotations/cache_claude_abelard
```

The premise (spec line ~226, plan Task 2 context) is that `data/annotations/cache` "already
holds the full corpus." **It does not.** Measured today:

| directory | files | unique guids |
|---|---|---|
| `data/annotations/cache` (the `CACHE` default) | 200 | **5,599** |
| `data/annotations/cache_merged` | 1,328 | **45,114** |
| `data/annotations/annotations.enGB.json` (production) | — | 45,114 |

`cache_merged`'s key set is an **exact** 45,114/45,114 match for production; `cache` covers
only 5,599 of them. So the repeatable-`--cache-dir` fix is necessary but the documented
*invocation* rebuilds production from 5,599 + 572 lines and silently destroys the other
~39,500 — precisely the catastrophe the fix exists to prevent, one directory level up.

Required plan changes:

- The merge command in the plan (and the spec's "Data flow" diagram) must use
  `--cache-dir data/annotations/cache_merged` as the base, not `data/annotations/cache`.
  Ideally the plan should also say *why* in one line, so a future reader doesn't "simplify"
  it back to the default.
- **Task 2, Step 6 is wrong for the same reason.** It runs `merge_cache_dirs` on
  `../../data/annotations/cache` and expects a count "close to 45,114," claiming that dir
  "is the source `--merge` already uses in production." It will actually print **200 files /
  5,599 annotations**, and its parenthetical justification is factually false. An executor
  that believes the step may either panic unnecessarily or, worse, "fix" the discrepancy by
  proceeding to a real merge. Point the step at `cache_merged` and expect exactly 1,328
  files / 45,114 unique guids.
- Note this also means the plan's Task 2 context paragraph ("the corpus already has 1685
  duplicate text_keys across cache files today") is slightly off: 1,685 is the corpus-wide
  count in `conversations.enGB.json`; the count within `cache_merged` is 1,680 duplicate
  keys (2,682 extra occurrences), and within `cache` it's 117. The point stands; the number
  should be right in a regression-test comment that future readers will trust.

### 2. The first post-fix `--merge` will not reproduce current production — flag it before anyone runs it

I simulated the plan's exact merge (`merge_cache_dirs([cache_merged])` with sorted glob,
then `reconcile_sarcasm_emotion`) and compared field-by-field against the shipped
`annotations.enGB.json`:

- Key sets match exactly (good).
- **487 records differ in at least one field; 115 differ in `emotion`.** Examples:
  `cf77b899…` sorted-merge says `dramatic`, production says `neutral`; `bfa8db93…`
  sorted-merge says `commanding`, production `neutral`.

Some of this is the sorted-order change picking different (deterministic) winners among
cache_merged's 1,680 duplicate keys; some may be production having been built from an
earlier cache state. Either way, the plan currently implies the `sorted()` change is a
no-op for real data ("fixes nondeterminism"), and it is not: the first merge after this
lands will silently change ~115 shipped emotion labels even with zero Abelard involvement.

Required plan change: add an explicit migration step to Task 2 — before the first real
`--merge` after the change, back up `annotations.enGB.json` and run
`diff_cache_vs_production.py data/annotations/cache_merged` so the ~115 flips are reviewed
as their own event, separate from the Abelard review. One sentence in the plan is enough;
silent is not acceptable here because the whole point of this work is *not* silently
changing production.

## Real but minor findings

### 3. Negative `--chunk` index is silently accepted by `interactive_next.py`

Plan Task 4 code, `main()`: the bounds check is `if args.chunk_index >= len(ranges)`.
`interactive_next.py <guid> -1` passes it and `ranges[-1]` happily renders the **last**
chunk with a header reading `chunk 0/N` — a silent wrong render in a tool whose entire
purpose is showing the labeler the right context. `interactive_submit.py` fails safe
(`canonical_chunk` never returns -1, so the required set comes out empty and any real
submission errors as "unexpected guids"), but the error message won't say why. Add
`chunk < 0` to both bounds checks.

### 4. Intra-conversation duplicate text_keys render as duplicate `>>>` targets

`render()` in Task 4 marks lines by *key membership* (`if key not in idx_by_key`), and
`abelard_targets()` dedupes but `dialogue_lines()` does not — so both physical occurrences
of a duplicated text_key render as targets. This is not hypothetical: in the real corpus,
`LucidIdira_dialogue` has Abelard target key `2d64a171…` at dialogue positions 22 **and**
36 (dialogue length 53, so it's chunked at the 50/10 defaults), and both positions fall in
retained chunk 0. That chunk's footer will print `Targets in this chunk: 2d64a171-…,
2d64a171-…` — twice — while `interactive_submit.py` requires it once. Submission still
works, so this is cosmetic, but it will confuse the labeler mid-corpus right at a line the
plan itself calls out as the dedup motivator. One-line fix: mark only the occurrence whose
position equals `idx_by_key[key]`, render the other as a normal line (or as `···`).

### 5. `interactive_next.py` hardcodes the pace/nonverbal lists, violating the plan's own Global Constraint

Global Constraints say "pace/nonverbal validation reuses `schema.PACES`/`schema.NONVERBALS`
exactly — do not redefine these lists," but Task 4's code defines
`PACES_LINE`/`NONVERBAL_LINE` as string literals. If `schema.NONVERBALS` ever changes, the
harness shows the labeler a vocabulary the submit script no longer accepts. Import them and
`", ".join(...)` — same cost, no drift. (The 21-word emotion vocab is correctly loaded
from `speaker_vocab.json`; only these two lines are hardcoded.)

### 6. The `CLAUDE.md` citation in Task 4 Step 4 is fabricated

The plan says: "Per this project's hard rule against `rm`/`rm -rf` — see `CLAUDE.md` —
always `gio trash`." `CLAUDE.md` is 13 lines and contains no such rule (it's entirely about
the `humanizer` skill for public writing). The advice itself is fine, but the executor will
be an agent that may go looking for the rule, and invented citations in plan documents get
copied forward into future plans. Either drop the citation or add the rule to `CLAUDE.md`
for real. (Also unverified: whether `gio` exists on this machine — check before relying on
it in the step.)

### 7. Malformed submission JSON crashes with a traceback instead of a clean error

`run()` in Task 3 does `json.loads(raw)` outside the `SubmitError` net, and
`validate_submission` assumes each label value is a dict (`rec.get(...)` — a bare
`{"guid": "resigned"}` string value raises `AttributeError`). The input is hand-authored
JSON produced in a hurry, dozens of times per session; a syntax error or a malformed record
is a *when*, not an *if*, and a raw traceback breaks the otherwise clean
validate-then-write contract the spec promises. Wrap the parse in `SubmitError("invalid
JSON: …")` and type-check each record before validating it. Cheap; do it now rather than
after the first mid-corpus crash.

## Verified correct — no action needed

I checked these plan claims against the real repo and they hold:

- **The canonical-chunk policy resolves the overlap double-labeling problem from my spec
  review.** `canonical_chunk()` assigns each overlap-zone target to exactly one chunk;
  `required_targets_for_chunk` enforces it on the write path; `render()` shows
  non-canonical duplicates as `···` context. I had measured 63 target occurrences in two
  chunks at 50/10 — all are now single-owner by construction.
- **The cross-conversation dedup resolves the duplicate-text_key merge-collision problem.**
  `scan_already_labeled_keys` + `exclude_path` means each text_key is written at most once
  into the interactive cache dir, enforced on both the read (`interactive_next`) and write
  (`interactive_submit`) paths. The resubmit-excludes-own-file wrinkle is real and handled
  correctly; I traced `test_run_resubmitting_same_chunk_…` by hand and it exercises exactly
  that path.
- **The `LucidIdira_dialogue` intra-conversation duplicate is real** (verified: key
  `2d64a171…`, positions 22 and 36), and deduping inside `abelard_targets()` at the source
  is the right place for it.
- **The pytest convention works as claimed**: bare `from annotate import …` imports, no
  `conftest.py`, `cd tools/annotate && python3 -m pytest` — I ran the existing suite, 11
  passed.
- **"23,689 real lines lack a `speaker` key entirely"** — exact, and it's genuinely a
  missing key (not an empty dict), so the defensive test is well-founded.
- **`BathTime_dialogue` is confirmed multi-chunk at 50/10** — 423 dialogue lines, 16
  targets, 11 raw ranges, 2 retained after dropping target-less ranges — so Step 3b's
  out-of-range-chunk smoke test is valid. (Worth knowing, not changing: the labeler will
  only ever see ~100 of BathTime's 423 lines. That is the spec's intended drop-target-less-
  chunks behavior, and the targets cluster, so context loss is limited — but if labeling of
  that conversation feels context-starved, the escape hatch is a bigger `--chunk-size`,
  which the design already supports.)
- **`validate_chunk_params`** correctly closes the `overlap >= chunk_size` infinite-loop
  hole from my spec review.
- **The `sorted()` determinism tests** in Task 2 correctly encode last-in-sorted-order-wins
  and will catch a reverted `sorted()`.
- **Task 3's validation order and error semantics** (exact-set match, per-field checks,
  nothing written on failure, `text_hash` via the same sha1[:12]) match both the spec and
  `annotate.py`'s existing conventions.

## Bottom line

Fix Finding 1 (wrong base dir in the documented merge + Task 2 Step 6) and Finding 2 (add
the backup-and-diff migration step) **before execution** — both are plan-text edits, no
design change. Findings 3-7 are small code edits worth folding into Tasks 3/4 now rather
than discovering mid-corpus. Everything else in the plan, including both advisor-driven
dedup fixes, checks out against the real data.
