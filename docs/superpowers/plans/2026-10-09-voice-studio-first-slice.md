# Voice Studio, first slice: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Speakers section of Voice Studio (Vue 3 app + local Python API) so it replaces the voice audit page (:8907) and the Pasqal lab (:8910).

**Architecture:** A stdlib Python API server (`tools/studio/server`, port 8930) reads and writes the existing `data/` JSON files, serves audio from whitelisted roots, serves the built Vue app, and proxies live requests to the separate model process (`tools/voice_design/live_backend.py`, :8909). The Vue app (`tools/studio/web`) is organized as thin views, feature components, composables and Pinia stores. Offline views never touch the model; live controls are gated on a model-status store.

**Tech Stack:** Python 3.12 stdlib + pytest (server); Vue 3.5, TypeScript, Vite 5, Pinia 2, Vue Router 4, Vitest 2, @vue/test-utils (web); Node 22.

**Spec:** `docs/superpowers/specs/2026-10-09-voice-studio-design.md` (section 7 is this slice).

## How this plan is organized

The plan was split because the full text ran past 4,500 lines. This file is the overview and table of contents; the
tasks live in seven sub-plans under `docs/superpowers/plans/2026-10-09-voice-studio/`. Do them in order: later parts
consume the interfaces defined in earlier ones. Each sub-plan repeats the Global Constraints so it can be read alone.

| Part | Sub-plan | Tasks | Covers |
|---|---|---|---|
| 1 | [Server foundation](2026-10-09-voice-studio/01-server-foundation.md) | 1, 2, 3 | Python API: scaffold, config, router, speakers, profiles and takes. |
| 2 | [Server live calls and HTTP app](2026-10-09-voice-studio/02-server-live-and-api.md) | 4, 5, 6 | Python API: designed-voice state, model client, live generation, FX, routes and the HTTP app. |
| 3 | [Web foundation](2026-10-09-voice-studio/03-web-foundation.md) | 7, 8 | Vue app: scaffold, typed API client, utilities and stores. |
| 4 | [Web shell, speakers list, speaker state](2026-10-09-voice-studio/04-web-shell-and-speakers.md) | 9, 10, 11 | Vue app: audio player, shared components, app shell, speakers list, speaker context and profile bar. |
| 5 | [Source section (milestone M1)](2026-10-09-voice-studio/05-source-section-m1.md) | 12 | Vue app: real clips, supplied wav, candidate ranker, live design. Ends at milestone M1 (audition usable). |
| 6 | [Lines, options, FX and results](2026-10-09-voice-studio/06-lines-options-fx-results.md) | 13, 14 | Vue app: test lines, model options, post-processing, generation and results. |
| 7 | [Integration and verification](2026-10-09-voice-studio/07-integration.md) | 15 | Build, serve, browser verification, live-model check, docs. |

Milestone M1 (audition usable) is the end of part 5. **Pause there** and let the user audition the 12 pilot designed
voices before building parts 6 and 7. M1 needs the server (parts 1 and 2) as well as the web parts 3 to 5, because the
audition runs against the real API; start it by hand (`npm run build`, then `python3 -m studio_server`), since `run.sh`
only arrives in part 7.

The web parts compile and unit-test without the server (they mock the API client), so parts 3 to 5 can be written in
parallel with parts 1 and 2. They share one contract, the route table in part 2, Task 6.

## Global Constraints

- Local only: the server binds `127.0.0.1`; audio is extracted from the user's game files and is never published.
- File serving: resolve the path, require it to sit under one of `data/voices`, `data/render`, `data/studio`, `data/voice_design`, and to be a file; otherwise 404.
- Nothing in the app or the tests deletes files. Tests write only under pytest `tmp_path`; manual checks must not touch real audit/manifest data (back up and compare before/after).
- Do not run the real model or any GPU job in this plan's automated steps; use the mock backend. The real-model check is a manual step for when the user says the GPU is free.
- Do not `git commit` or `git push` unless the repo owner says so. Steps named "Checkpoint" run `git status` and stop. If the owner asks for commits: plain human messages, no AI/Claude attribution of any kind.
- Reuse existing JSON schemas as-is: `audit.json`, `design_manifest.json`, `overrides.json`, `scores.json`, `prompts.json`, `catalog.json`, `jobs.jsonl`, `export/index.json`, FX `scenarios.json` and `presets.json`.
- No magic numbers in frontend code; files under 500 lines; `<script setup lang="ts">`, order script / template / `<style scoped>`.
- Model backend states shown to the user: `down`, `ready`, `busy`. (Spec deviation: "loading" is shown as `down` because the backend only starts listening after the model is loaded.)
- API framework: stdlib `http.server` (spec open question resolved: FastAPI is not installed cleanly here and the existing tools are stdlib).

## Decisions that differ from the first spec draft

These were settled during planning and after Kimi's review, and are now recorded in the spec.

1. `data/pasqal_lab/` never held real data, so there is **no import step**; the Pasqal lab's profile shape is reused as-is.
2. "Set active" writes `data/studio/<slug>/active.json` (one canonical location for every speaker).
3. The studio carries its own `fx_apply.py` (importing `tools/fx_lab/batch.py`) instead of depending on `tools/pasqal_lab/`.
4. `options.seed` in a profile is a **policy**: blank = new random seed per line, a typed value pins every line.
5. Candidates without a recorded `gen` (all 12 pilot NPCs) are shown with a "no recorded seed" marker.
6. **Milestone M1** (audition usable) is the end of Task 12; pause there for the user to audition the 12 pilot voices before building Tasks 13 to 15.
7. The model status is polled for the whole session from the app shell (every 5 s; the health call is cheap and never touches the GPU), not only while a live control is visible as the spec first said.
8. The speakers page is a grouped full-page list (needs a voice / has a source / profile saved), not a sidebar with status dots. Same information; the sidebar arrives with the Pools slice.
9. `VoiceProfile.notes` exists in the schema but nothing writes it yet; no UI is planned for it in this slice.
10. The pinned web versions (Vite 5, Vitest 2, TypeScript 5.6) are old but mutually compatible; kept on purpose for a local tool, and easy to bump later.
11. `studio_server/design.py` puts `tools/voice_design` on `sys.path` to reuse its tested helpers. A future top-level `import design` elsewhere would resolve to the wrong module; if that bites, load the helpers with `importlib.util.spec_from_file_location` instead.

## Review Focus

Failure modes the spec implies but a straight reading would not test. Each has a test in the owning task.

1. **Two speaker names that slugify the same** (e.g. "Ulfar" / "ulfar!"): slugs must stay unique and stable, never collide on disk (Task 2).
2. **Bad paths from the browser**: a candidate-keep or clone reference that is missing, `..`-escaping, or outside `data/` must be a 400/404, never a copy or a read (Tasks 3, 4, 5, 6).
3. **Model dies mid-batch**: generation shows the backend error, stops, and keeps every take already made (Tasks 5, 14).
4. **Empty states**: a speaker with no lines, no real clips, no candidates, or no takes renders an empty-state message, not an exception (Tasks 2, 10, 12, 13, 14).
5. **Corrupt `takes.json`**: the server reports the problem and does not overwrite the file (Task 3).
6. **Large lists**: a speaker with 500+ lines must stay responsive (render cap with a "show more" control) (Task 13).

## File Structure

```
tools/studio/
  README.md                         run + dev instructions (Task 15)
  run.sh                            builds web if needed, starts server (Task 15)
  server/
    studio_server/
      __init__.py
      __main__.py                   python -m studio_server  (Task 6)
      config.py                     Config: repo paths, file roots, resolve_file, under_data  (Task 1)
      errors.py                     ApiError                                                   (Task 1)
      jsonio.py                     read_json / write_json_atomic                              (Task 1)
      router.py                     Request, Router                                            (Task 1)
      speakers.py                   speaker list/detail/lines                                  (Task 2)
      store.py                      profiles, takes, active                                    (Task 3)
      design.py                     candidate state: verdict/order/keep/description/generate   (Tasks 4, 5)
      model.py                      ModelClient (health + calls to live_backend)               (Task 5)
      clone.py                      clone generate + take record                               (Task 5)
      fx.py                         preset list + apply via fx_apply.py subprocess             (Task 5)
      fx_apply.py                   run under tools/fx_lab/.venv-fx                            (Task 5)
      routes.py                     builds the Router                                          (Task 6)
      app.py                        HTTP handler, static serving, make_server, main            (Task 6)
    tests/
      conftest.py                   make_repo fixture builds a tiny fake repo                  (Task 1)
      mock_backend.py               fake live_backend over HTTP                                (Task 5)
      run_mock_stack.py             serve the app on a fake repo + mock backend, for browser checks (Task 15)
      test_*.py
  web/
    package.json, vite.config.ts, tsconfig.json, index.html
    src/
      main.ts, App.vue, router.ts
      api/        types.ts, client.ts
      utils/      order.ts, seed.ts, fileUrl.ts, batch.ts, spread.ts
      stores/     model.ts, speakers.ts
      composables/ useAudioPlayer.ts, useSpeakerState.ts, useSpeakerContext.ts
      components/
        shared/   AppShell.vue, ModelStatus.vue, ClipCompare.vue, StarRating.vue, SectionCard.vue, EmptyState.vue
        source/   SourcePanel.vue, RealClipList.vue, SuppliedClip.vue, CandidateRanker.vue, DesignPanel.vue
        lines/    LinePanel.vue
        options/  OptionsPanel.vue
        fx/       FxPanel.vue
        results/  ResultsPanel.vue, TakeRow.vue
        profile/  ProfileBar.vue
      views/      SpeakersView.vue, SpeakerView.vue
```

Also modified: `tools/voice_design/live_backend.py` (`/health` reports `busy`), Task 5.

## Self-Review

**Spec coverage (spec sections to tasks)**

- 3 Information architecture, speaker page sections: Tasks 11 to 14 (Source, Test lines, Options, Post-processing, Results).
- 3.1 seed policy (one seed per line shared across sources): Task 8 `runBatch`, Task 14 Generate bar.
- 3.3 FX two levels and bridge: Task 14 `FxPanel` (link to the FX Lab). **Gap by design:** the "Open in FX Lab" send-the-take bridge is out of the first slice (spec section 7 lists FX Lab embed/bridge as not in the slice); the link covers navigation only.
- 3.4 live versus pre-recorded: Task 5 (health), Task 8 (model store), Tasks 12 and 14 (disabled with reason).
- 4 Data model, existing files reused: Tasks 2 to 4.
- 5 Architecture, API: Task 6 (stdlib, deviation recorded); file whitelist: Tasks 1 and 6.
- 7 First slice: Tasks 1 to 15; Pools, Matches, Render QA, FX port untouched.
- 8 Testing: pytest with mock backend (Tasks 1 to 6), Vitest (Tasks 7 to 14), browser checks with the Playwright MCP tools (Task 15 steps 4 and 5: real data with the model off, then a throwaway fake repo with the mock backend covering keep, generate, FX, register and rate; no scripted Playwright suite, to avoid a browser download dependency); real-model check as a manual step (Task 15, step 6).
- 9 Risks: seed reproducibility check (Task 15, step 6); data-layout import closed (decision 1).

**Placeholder scan:** after the advisor's and Kimi's reviews the fix-notes were resolved into final code (the `fx_apply.py` path, the unused imports, the `ClipCompare` unwrap, the stray type export and the candidate checkbox). A search for `TBD`, `TODO`, `fix this when writing`, `similar to Task` and `remove it when writing` finds nothing. Treat this and the other self-review lines as hints, not proof: two earlier self-review claims were wrong and were caught only by independent review.

**Type consistency:** `SpeakerContext` fields used in Tasks 12 to 14 match the Task 11 interface (`selectedSources`, `selectedLines`, `options`, `fxChosen`, `fxAvailable`, `chosenSources`, `upsertTake`, `load`, `slug`). `Take`, `Line`, `LiveTake`, `CloneRequest` are defined in Task 7 and used unchanged. `runBatch` arguments match between Task 8 and Task 14. Server function names in the Task 6 route table match Tasks 2 to 5.

**Review Focus coverage:** slug collisions (Task 2), bad paths (Tasks 1, 3, 4, 5), model dies mid-batch (Tasks 5 and 8 and 14), empty states (Tasks 2, 10, 12, 13, 14), corrupt takes.json (Task 3), large lists (Task 13).

## Changes after the advisor's review (2026-10-09)

1. **Register pick.** Replacing the old audit page would have dropped "Register picks", the only path from an audition verdict into `plan.py`. Added `POST /api/speakers/{slug}/register` (part 2, Task 4 and Task 6), `api.register`, `registerPick()` and a "Register pick" button (part 4). A speaker named in the design manifest stays `designed` after registration, and its registered clip (and any prompt-bank-only clips such as the narrator's) now appear in the Source section (part 1, Task 2).
2. **Options panel** read `.value` on an already-unwrapped ref; it now goes through `ctx.options.value` (part 6, Task 13).
3. **M1 prerequisites** are explicit: Tasks 1 to 12 done, then build and start the server by hand (part 5, Task 12 step 6).
4. **Concurrent writes.** One `STATE_LOCK` around every read-modify-write of `takes.json`, `audit.json`, `overrides.json`, the manifest and `prompts.json` (parts 1 and 2); `runBatch` now awaits `onTake`, so "done" no longer appears while FX is still running (part 3, Task 8).
5. **Unhandled exceptions** (for example a missing key in a request body) now answer `500 {"error": ...}` instead of dropping the connection (part 1, Task 1; test in part 2, Task 6).
6. **Placeholders resolved:** the `fx_apply.py` path, the unused imports, the `ClipCompare` unwrap, the stray type export, and the candidate-as-clone-source checkbox now have final code and a test.
7. `App.vue` keys the router view by full path so moving speaker to speaker rebuilds the page state (part 4), and the design panel's description follows reloads (part 5).

## Review gates

Execution is native (one builder), with an **independent review at M1 and again after Task 15**: a fresh reviewer reads the finished tree against the spec. The defects found so far were integration-level (a verification step that expects the wrong group count, a button whose label and server behaviour disagree), which is what the author of both sides tends to miss.

## Changes after Kimi's plan review (2026-10-09)

1. Task 15's real-data checklist expected three groups; it is now two (empty groups are hidden).
2. Task 15 gains a GPU-free browser pass against the mock backend (`tests/run_mock_stack.py`) covering keep, generate, apply FX, register and rate.
3. "Re-apply FX" with an empty picker repeats the take's own presets instead of clearing the FX.
4. Results rows include a playable `source clip` next to bank, raw clone and FX.
5. `design/keep` backfills the description and sample text from the speaker's saved values and rejects a take with no seed, so every kept candidate can be regenerated.
6. A catch-all handler for unexpected errors was already added after the advisor's review; `subprocess` timeouts in FX now answer a 500 JSON error as well. `GET .../takes` for an unknown speaker is a 404.
7. Decisions 7 to 11 above record the polling, list layout, unused `notes`, version pins and `sys.path` choices.
