# Voice Studio, Render QA section: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native) or subagent-driven-development.

**Goal:** Replace `tools/render_corpus/audit_server.py` (:8913/8951) with a Render QA section: listen to rendered clips (the merged export or one render run), see the auto flags, judge good or bad with tags and a note, and compare against the clone reference, the earlier render and the game's own voice, writing the same verdict files as today.

**Architecture:** `studio_server/qa.py` indexes clips from `data/render/export/index.json` (or `data/render/<run>/manifest.jsonl`) with the same auto flags as the old page, filters, sorts and pages them on the server (the export has about 11,000 clips), and reads and writes `data/render/audit/verdicts[_<run>].json`. Audio is served by the existing `/file` route; the compressor A/B playback goes through one new route that calls the existing `deburst` code lazily.

**Spec:** parent spec T5 (Render QA).

## Global Constraints

As in the Pools plan: local only, nothing deletes files, no commits or pushes unless asked, dark UI only, no magic numbers, files under 500 lines. Verdict files keep their format `{guid: {verdict: "good"|"bad", tags: [..], note: ""}}`, written atomically on every click. Server tests `cd tools/studio/server && python3 -m pytest tests -q`; web `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`.

## Decisions

1. **Same flags as the old page**, reimplemented in `qa.py` (not imported: `audit_server.py` pulls numpy and a module-level HTML path): `cap_hit` (27.0 to 30.2 s), `slow` (under 7 chars/s, 8+ chars), `fast` (over 26), `short` (under 0.7 s), `very_long` (over 40 s), plus the flags the render already stored and, in run mode, `asr.jsonl` flags with `heard` and `wer`.
2. **Server-side filtering and paging.** Clips are cached per source keyed by the index or manifest mtime. The list endpoint takes filters and a page; a facets endpoint returns the filter options and counts.
3. **Sorts:** `suspicious` (most flags first, then distance from 15 chars/s), `slowest`, `fastest`, `longest`, `shortest`, `random` (seeded so paging is stable).
4. **Audio** is played through `/file?p=` for the clip, its clone reference (`data/voices`), the earlier export render and the real VO snippets (`data/render/<run>/real/`), all under whitelisted roots. Compressor playback uses `GET /fx-file?p=<path>&fx=<mild|strong>`: it must be a whitelisted wav and calls `deburst` lazily; if numpy or scipy is missing the route answers a clear 501. Results are cached in memory by path, preset and mtime.
5. **Verdict writes** take `STATE_LOCK`; a bad verdict value is a 400; `verdict: null` clears the entry. The old page and the studio share the files, so use one at a time.
6. **Keyboard:** j/k move, space play, g good, b bad, u clear, n next unjudged, x compressor on/off, as on the old page, in a composable with a pure key-to-action function.

## File structure

```
tools/studio/server/studio_server/qa.py            clips, flags, filters, facets, verdicts      (Task 1)
tools/studio/server/studio_server/routes.py, app.py  + /api/qa/*, /fx-file                        (Task 2)
tools/studio/server/tests/test_qa.py, test_qa_http.py
tools/studio/web/src/api/types.ts, client.ts, stores/qa.ts, composables/useQaKeys.ts, utils/qaKeys.ts
tools/studio/web/src/components/qa/QaFilters.vue, QaRow.vue
tools/studio/web/src/views/QaView.vue, router.ts, AppShell.vue (nav)
```

## Tasks

### Task 1: `qa.py`
- `runs(cfg) -> [{id, label, clips}]` (the export as `export`, then every `data/render/<name>/manifest.jsonl`).
- `auto_flags(dur, chars, existing) -> list`, `spoken_text(t)`.
- `clips(cfg, run) -> list[dict]` with `guid, wav (repo path), text, context, speaker, engine, voice_source, dur, cps, ref, ref_path, emotion, instruct, flags, old (path or null), real (list), heard, wer`; unreadable wavs are skipped, missing run is 404.
- `facets(cfg, run)`, `page(cfg, run, *, speaker, ref, engine, flag, verdict, q, sort, seed, offset, limit)` returning `{total, items, stats: {good, bad, unjudged}}`, items carrying their `verdict`.
- `get_verdicts(cfg, run)`, `set_verdict(cfg, run, body)`.
- Tests (fake repo: a tiny export with 6 clips of chosen durations and texts, one run with `manifest.jsonl`, `asr.jsonl`, `real.json`): each flag threshold and its boundary, text cleaning, the export and run listings, 404 for an unknown run, every filter, each sort, stable random with a seed, paging and the limit cap, verdict set / clear / bad value, the verdict file name per run, stats counts, a wav that cannot be read is skipped, clip cache invalidates when the index mtime changes.

### Task 2: routes and compressor audio
`GET /api/qa/runs`, `GET /api/qa/facets?run=`, `GET /api/qa/clips?...`, `POST /api/qa/verdict`. In `app.py` add `GET /fx-file` (whitelist check via `cfg.resolve_file`, preset must be `mild` or `strong`, lazy `deburst` import from `tools/render_corpus`, 501 when unavailable, cache). Tests: HTTP flow; `/fx-file` 404 for a non-whitelisted path, 400 for a bad preset, and a real call on the fake wav when numpy and scipy exist (skip otherwise).

### Task 3: web
`utils/qaKeys.ts` (`keyAction(key) -> action|null`, tested), `composables/useQaKeys.ts` (binds on mount, ignores inputs and selects, removes on unmount), store (`loadRuns`, `loadFacets`, `loadPage`, `setVerdict` with optimistic update and rollback, `filters`), `QaFilters`, `QaRow` (meta line, text, flags, heard text, `ClipCompare` with clip / reference / old / real VO, Good and Bad buttons, tags, note), `QaView` (run picker, filters, stats line, paging, selection and keyboard, compressor select). Vitest: key map, store optimistic update and rollback, row emits verdict/tag/note, filters emit, view paging and keyboard moves.

### Task 4: verification and docs
Full suites; real-data pass on the export (11,051 clips: filter by flag, play one clip and its reference, set and clear a verdict on a throwaway copy of `verdicts.json` and restore the real file byte-for-byte); compressor playback returns audio; README and CLAUDE.md lines.

## Self-review

Spec coverage: T5 Render QA (Tasks 1-3). The earlier-render and real-VO comparisons are preserved. Not in scope: running the render, the ASR check (`asr_check.py` stays a command-line tool whose output the page reads).
