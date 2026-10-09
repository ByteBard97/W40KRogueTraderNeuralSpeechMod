# Voice Studio, Matches section: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native) or subagent-driven-development.

**Goal:** Replace `tools/npc_profile/match_review.py` (:8913) with a Matches section: confirm or overrule each proposed roster-entry-to-known-speaker match, saving to the same `data/npc_profile/match_decisions.json`, and keep the Pools routes in step with the decisions.

**Architecture:** `studio_server/matches.py` builds the review rows with the same logic as `match_review.build_rows` (the roster, `known.match`, `build_known`), reusing the Pools service's cached loaders. It is now the only writer of `match_decisions.json`. Saving a decision rebuilds the pools if they exist, so the routes never disagree with the verdicts. A `MatchesView` replaces the old HTML page.

**Spec:** parent spec T5 and the Pools spec decision 2 (routing consumes `match_decisions.json`).

## Global Constraints

As in the Pools plan: local only, nothing deletes files, no commits or pushes unless asked, dark UI only, no magic numbers, files under 500 lines. `match_decisions.json` keeps its format: `{"<conversation>|<roster id>": "accept"|"reject"}`, conversation names exactly as stored; an empty value removes the key. Server tests `cd tools/studio/server && python3 -m pytest tests -q`; web `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`.

## Decisions

1. **Defaults match the old page:** a flagged row (gender warning or ambiguous match) starts undecided; a clean row counts as accepted until the user says otherwise. Only explicit choices are stored.
2. **Groups** in the order the old page used: Flagged, Clean with a voice bank, Clean without a bank.
3. **One writer.** The old page stays on disk until the user approves trashing it; the studio does not call it. If both are ever open the last write wins, so the plan says in the README to use one.
4. **After a save**, if `data/studio/pools.json` exists, call `pools.rebuild` (overrides and spot-check marks survive) and report `{"pools_rebuilt": true, "queue_entries": n}`; if it does not exist, report `false`.
5. **Samples** come from the unnamed jobs' text (every roster line that matters is an unnamed job); lines not in `jobs.jsonl` show no sample. The old page's gap markers ("other speakers' lines in between") are kept, using the roster line numbers.
6. **Page size:** rows are filtered and paged on the server (default 50, cap 200), because the real data has about 277 matches.

## File structure

```
tools/studio/server/studio_server/matches.py       rows, decisions, save                  (Task 1)
tools/studio/server/studio_server/routes.py        + /api/matches routes                   (Task 2)
tools/studio/server/tests/test_matches.py, test_matches_http.py
tools/studio/web/src/api/types.ts, client.ts, stores/matches.ts
tools/studio/web/src/components/matches/MatchRow.vue, MatchFilters.vue
tools/studio/web/src/views/MatchesView.vue, router.ts, AppShell.vue (nav)
```

## Tasks

### Task 1: `matches.py`
- `rows(cfg) -> list[dict]` with fields `id, conversation, entry, name, label, gender, species, role, evidence (3), lines, samples (3), gaps, speaker, has_bank, speaker_lines, game_gender, warning, ambiguous_with, flagged`, ordered flagged first, then with bank, then by speaker and conversation.
- `decisions(cfg) -> dict`, `effective(row, decisions) -> "accept"|"reject"|""` (default per decision 1), `page(cfg, *, group=None, speaker=None, state=None, q=None, offset=0, limit=50) -> {total, counts, items}` with each item carrying `decision` (stored value or `""`) and `effective`.
- `save(cfg, id, value) -> {pools_rebuilt, queue_entries?}`: value must be `""`, `accept` or `reject`, else 400; the id must be a known row, else 404; atomic write under `STATE_LOCK`; `""` removes the key; then decision 4.
- Tests on the pool fixture (extend the fixture so two entries match: C1|a Heinrix has a bank, C1|b Tervantias has none; add a flagged one by giving a second known speaker the same tokens): rows and ordering, groups and counts, default-accept for clean and undecided for flagged, save accept/reject/clear, bad value 400, unknown id 404, the file keeps its old keys, pools rebuilt after a save when `pools.json` exists and not otherwise, a rejected row changes the pools route (reuses Task 3 of the Pools plan), paging cap.

### Task 2: routes
`GET /api/matches?group=&speaker=&state=&q=&offset=&limit=`, `POST /api/matches/decision` body `{id, value}`. HTTP test walks list, save, 400, 404.

### Task 3: web
Types, client, store (`load`, `setDecision` with optimistic update and rollback on error), `MatchFilters` (group, speaker text, state: any/undecided/accepted/rejected), `MatchRow` (select, name and label, proposed speaker with bank chip, game gender, evidence, samples, warnings), `MatchesView` (counts line, filters, rows, show more). Vitest: store rollback, row emits the chosen value, filters emit, view loads and pages.

### Task 4: verification and docs
Full suites; real-data pass: counts match `match_review.py --dump` (277 rows, 25 flagged: run the dump to compare); change one decision on a throwaway copy of `match_decisions.json` (back up and restore the real file byte-for-byte; the real file has 25 entries); README and CLAUDE.md lines.

## Self-review

Spec coverage: T5 matches (Tasks 1-3), the Pools decision 2 handshake (decision 4, Task 1 test). Types: row `id` is the same key the Pools engine builds with `entry_key`.
