# Voice Studio: design spec

Status: draft for review (2026-10-09). Not implemented. Author: Claude, with the project owner.

## 1. Why this exists

### 1.1 The project in one paragraph

This repo adds neural speech to Warhammer 40,000: Rogue Trader. The game's text-only lines were previously voiced by
another modder's Chatterbox TTS (the "AIVO" bank, ~38,000 clips). We are replacing those clips with our own renders
(VoxCPM2 and Qwen3-TTS, cloned from real game clips where they exist) and rebuilding the Wwise sound bank. About 11,000
lines (companions, narrator) are already replaced. About 27,000 are not, and the biggest block is **12,918 priority-3
conversation lines spoken by characters we have no voice for** (6,201 lines from 299 named NPCs, 6,717 lines with no
speaker; counts from `data/render/jobs.jsonl` as regenerated 2026-10-08, after about 2,400 unquoted lines were
re-planned as narrator).
Those still play the old Chatterbox audio. Generating good voices for them, and fixing the companions whose clips are
poor, is the main remaining work.

### 1.2 The problem with the tooling today

The work is done through about nine small single-file HTML pages, each with its own Python server and port
(8900-8951), its own state file, and (for the audio pages) its own audio player. Port assignment is informal: the code defaults
of `match_review.py` and `render_corpus/audit_server.py` both use 8913, and `queue_server.py` defaults to 8920, the
same as the port `match_review` is run on. The ports below are the ones the handoffs actually use. The active pages are:

| Page | Port | Purpose |
|---|---|---|
| `tools/voice_design/audit.html` | 8907 | Audition designed NPC voices; accent/fit/reject/pick; live design (new) |
| `tools/pasqal_lab/index.html` | 8910 | Clone-lab for one speaker (Pasqal); reference clips, options, FX, takes, profiles (new) |
| `tools/fx_lab/index.html` | 8908 | Faust effect chain in the browser (77 knobs, 23 blocks), presets |
| `tools/npc_profile/match_review.py` | 8920 | Review of roster-to-known-speaker matches |
| `tools/render_corpus/audit.html` | 8951 | Listen to rendered output and mark verdicts |
| `tools/render_corpus/queue_server.py` | 8950 | Render queue (API only) |

The rest (`tts_bakeoff/*`, `emotion_review/*`, `listening_test`, `scorer/review_server.py`) belong to finished studies
and are out of scope. The active pages share one workflow (choose a voice, rank candidates, clone-test it, tune
post-processing, register it) but have no common notion of a "speaker", no shared player, and no shared view of whether
the GPU model is running. Each is vanilla JS built with string templates; the audit page is 315 lines of string
templates. The stronger reason for an app is the first one: five tools, five state files and no shared notion of a
speaker, with a lot of listening and tuning still to do.

### 1.3 Goals

1. **One place to do the remaining voice work**, organized around the thing we are producing, not around the old pages.
2. **Fast listen-compare-decide loops.** Every decision here is by ear, so the common operation is "play these N clips
   side by side and record a verdict". This must be one click per comparison and never interrupt the user's place.
3. **Reproducibility.** Any voice or take that the user likes must be re-creatable: seed, model options, source clip and
   FX preset are recorded with it.
4. **Work offline from the model.** Browsing, ranking, comparing and reviewing pre-recorded audio must work when the
   GPU backend is off (the 5080 is shared with another project and is only available at times).
5. **Do not disturb existing state.** The new app reads and writes the same JSON files the old pages use, so both can
   run during the migration.

### 1.4 Non-goals

- Replacing the render pipeline, the bank patcher (`tools/bnk_patch`) or `plan.py`. The app produces decisions and
  profiles; wiring them into rendering is separate work.
- Re-implementing the Faust FX engine. FX Lab is embedded first (see 6).
- Public hosting. The app plays audio extracted from the user's game files and runs locally only.
- Similarity scoring or other automatic judging. That is a separate tool (`tools/scorer`).
- Migrating the finished Abelard studies.

## 2. The tasks the app must support

### T1. Named NPC with a real source clip (companions such as Pasqal)

Choose which of the speaker's real clips to clone from (Pasqal has 45, 12 curated), pick a representative set of
his lines across emotions, render them with the model, and compare against the original clip, the current bank render
and the raw clone. Tune model options (cfg, timesteps, seed, retry, text normalization, style prefix, continuation
mode). Choose FX presets and hear the result. Save the winning combination as the speaker's profile.
Known difficulty: Pasqal's source clips are already heavily vox-processed, so clones inherit and may double the
processing, and the accent may partly be a processing artifact. The comparison view exists to make that audible.

### T2. Named NPC with no source clip (299 speakers, ~6,200 lines)

Generate candidate voices from a text description (design mode: one description, many seeds), rank them best to worst,
mark accent/fit/reject, and promote rank 1 as the speaker's source clip. The design step is live and iterative: roll a
new seed, listen, keep or discard. Kept candidates record seed, cfg, timesteps and description so they can be
regenerated on the same machine. After promotion the speaker proceeds as in T1 (clone from the designed clip, tune,
FX, profile). The top ~80 speakers get their own voice; the rest share pooled voices (T3).

### T3. Unnamed NPCs (~6,700 lines with no speaker, plus the minor-character tail)

No individual identity exists, so the unit is a **voice pool slot** (e.g. "old male human", "young female human",
"ork", "servitor"), not a speaker. The user defines slots, creates a source voice for each (same design/clone/FX
tooling as T1/T2), and each line is assigned to a slot. Assignments come from the speaker-attribution harness
(`tools/npc_profile`, gender/species/age labels). **Recommended policy** (not yet confirmed by the user): assign
automatically from harness labels; the user reviews an exception queue (low confidence, conflicting labels) plus a
per-slot spot check of ~10 sampled lines, instead of approving every line.

### T4. Post-processing (FX) authoring and application

Two levels, kept deliberately separate:
- **Authoring**: build and tune effect chains on any clip (the existing FX Lab: Faust chain, 77 knobs). Output is a
  global preset library plus a **label-to-preset map** for the harness's effect labels (`machine`, `vox_channel`,
  `helmet`, `ethereal`, `monstrous`, `cavernous`). `tools/fx_lab/batch.py` has no notion of labels: it reads
  `data/fx_lab/assignments.json` as `{"speakers": {name: [presets]}, "lines": {guid: [presets]}}` (per-line beats
  per-speaker, presets chain in series). Decision: **`batch.py` stays untouched**. The label map is studio-internal
  state, and the studio expands labels into per-speaker and per-line entries when it writes `assignments.json`.
  Nothing writes that file yet. This authoring work is outside the first slice.
- **Application**: inside a speaker or pool slot, choose preset(s) from the library and A/B them on real takes.

### T5. Review of matches and rendered output

- **Matches**: confirm or overrule ~277 roster-to-known-speaker matches (25 flagged).
- **Render QA**: listen to samples from a render run, mark good/bad, find dropped words and wrong voices before
  installing audio in the game.
These review whole sets rather than one speaker, so they are separate sections.

### T6. Handing results to the pipeline

Profiles are saved JSON; "Set active" for a speaker copies the profile to its canonical location so `plan.py` and
`batch.py` can later consume it. Wiring those consumers is outside this spec.

## 3. Information architecture

Organized by the artifact each section produces.

| Section | Produces | Tasks |
|---|---|---|
| **Speakers** | A voice profile per named speaker | T1, T2 |
| **Pools** | Pool slots (each a profile) and a line-to-slot assignment map | T3 |
| **FX Lab** | Preset library; label-to-preset map (studio-internal, expanded into `assignments.json`) | T4 (authoring) |
| **Matches** | Verdicts on speaker matches | T5 |
| **Render QA** | Verdicts on rendered clips | T5 |

Top-level navigation is a persistent top bar with these five entries plus a model-status indicator. Speakers and Pools
each have a sidebar list (speakers with a status dot: no voice / has source / profile saved; slots likewise).

### 3.1 Speaker page: sections on one scrolling page, not tabs

The work is iterate, listen, adjust. Tabs force leaving the results to change a setting. One page, five collapsible
sections, with a sticky results area:

1. **Source**: where the clone reference comes from. Branches by origin:
   - *real*: list of the speaker's catalog clips (play, duration, transcript, noise level, curated rank); tick one or
     several to compare.
   - *designed*: description editor, **live design** (seed, cfg, steps, Generate, Keep), candidate ranker with
     drag-to-order and accent/fit/reject, rank 1 = source.
   - *supplied*: a wav path under `data/` plus transcript.
   Sections that do not apply to the speaker's origin collapse; a voiceless speaker with no kept candidate shows the
   designed branch open.
2. **Test lines**: the speaker's lines (searchable, emotion filter chips, bank render playable), checkboxes, "pick 6
   spread across emotions".
3. **Options**: cfg, timesteps, seed policy, style prefix from annotation, retry bad takes, normalize text,
   continuation mode (off by default; it can echo the reference audio, see `tools/tts_engines/voxcpm2.py`).
4. **Post-processing**: FX preset picker (multi-select, applied in series), "Open in FX Lab".
5. **Results**: per line, a `ClipCompare` row (real clip, bank render, raw clone, FX version) plus star ratings.

Seed policy when comparing sources: one seed per line shared across all selected sources, so differences come from the
source clip, not luck. A blank seed picks one random seed per line.

### 3.2 Pool page

Slot list plus an editor that reuses the Speaker page's Source/Options/Post-processing sections for the selected
slot, and an **Assignment** view: lines grouped by slot, filters (confidence, gender, species, slot), per-line override,
exception queue, and a 10-line sampled spot-check per slot.

### 3.3 FX at two levels, with a bridge

Authoring lives in the FX Lab section (embedded Faust page first). Application is the picker inside speakers and
slots. "Open in FX Lab" sends the current take; saving a preset there returns the preset name to the profile. One-way
and simple; no live link between the two audio engines.

### 3.4 Live versus pre-recorded

A single `useModel` store exposes `down | ready | busy` from the backend's health endpoint (polled every 5 s from the
app shell for the whole session; the call is cheap and never touches the GPU). Every live control (Generate, live design, Apply FX that needs the model's output) is
disabled with a stated reason when the state is not `ready`. Offline views (rank, compare, review, browse) never call
the model and never depend on that store.

## 4. Data model

The central object is the **voice profile**. Existing files are read as they are; the app does not introduce a new
schema for data that already has one.

```
VoiceProfile {
  name: string                 // speaker name or pool slot name
  kind: 'speaker' | 'slot'
  source: { wav: string, text: string, origin: 'real' | 'designed' | 'supplied' }
  options: { cfg, timesteps, seed, use_instruct, retry_badcase, normalize, continuation }
  fx: string[]                 // preset names, applied in series
  test_lines: string[]         // guids
  notes: string
  saved: timestamp
}
```

Existing state the app reads/writes (all under `data/`):

| File | Content | Used by |
|---|---|---|
| `voice_design/design_manifest.json` | per-NPC description, test sentence, candidates, `gen` (seed/cfg/steps per candidate, only for candidates made after seeding was added; the 12 pilot NPCs have none) | Source (designed) |
| `voice_design/audit.json` | per-NPC `cands{cN:{accent,fit,reject}}`, `pick`, `order` | ranker |
| `voice_design/overrides.json` | edited descriptions for redo | Source (designed) |
| `studio/<slug>/{profile,takes,active}.json` | saved profiles, takes with ratings (new; written by the studio) | Results, profiles |
| `voices/catalog.json`, `voices/prompts/prompts.json` | extracted real clips; curated reference bank | Source (real) |
| `render/jobs.jsonl`, `render/export/index.json` | planned jobs (speaker, text, annotation, voice_source); installed renders | Test lines, bank clip |
| `npc_profile/match_decisions.json`, `roster_35b_all.json` | match decisions; speaker attribution | Matches, Pools |
| `fx_lab/presets.json`, `tools/fx_lab/scenarios.json` | saved and built-in FX presets | Post-processing |

`data/pasqal_lab/` does not exist: the Pasqal lab was built but never used, so there is nothing to import. The studio
simply starts writing per-speaker state under `data/studio/<speaker-slug>/`, reusing the lab's profile and take shapes.
Candidates with no recorded `gen` (all 12 pilot NPCs) are shown with a "no recorded seed" marker: for them the WAV is
the only reproducible artifact.

**Seed policy.** `options.seed` in a profile is a policy, not a value: blank means a new random seed per line (shared
by all sources for that line); a typed value pins every line to it. The UI labels this explicitly.
**Naming.** The profile's `continuation` option maps to sending `prompt_text` to the backend; `use_instruct` maps to
sending `instruct`.

New files: `data/studio/<slug>/profile.json`, `takes.json`; `data/studio/pools.json` (slots, assignments);
`data/fx_lab/assignments.json` (written by a later slice, in the format `batch.py` already reads).
Per-line pool assignments (later slice) record provenance: `auto` or `override`, plus the harness confidence at
assignment time, so a re-run of the harness can be diffed instead of silently overwriting the user's decisions.

## 5. Architecture

```
Browser (Vue 3 + TS + Vite + Pinia)
   │  fetch /api/*  and  /file?p=…  (audio)
   ▼
Studio API server (Python, local, one process)      ──►  Model backend (separate process, GPU)
   reads/writes data/** JSON, whitelists file roots        tools/voice_design/live_backend.py :8909
   proxies /api/live/* to the backend                      VoxCPM2 in memory, one generation at a time
   runs FX via tools/fx_lab/.venv-fx (studio's own fx_apply.py)
```

- **Frontend**: Vue 3, `<script setup lang="ts">`, Vue Router, Pinia, Vitest. Built with Vite; served as static files
  by the API server in normal use and by the Vite dev server in development.
- **API server**: Python stdlib `ThreadingHTTPServer`, one thread per request, so a long model call never blocks
  health polling or audio serving. FastAPI was considered (typed routes, OpenAPI) and not chosen for the first slice:
  it is not cleanly installed here and there are only about 20 routes whose validation is a few tested lines. It can be
  swapped later behind the same route table. File serving keeps the existing rule: resolve the path and require it to
  sit under a whitelisted root (`data/voices`, `data/render`, `data/studio`, `data/voice_design`).
- **Location**: `tools/studio/` (`server/` for the API, `web/` for the Vue app; the built bundle is `web/dist`, served by
  the API server). Repo-root `src/` is the C# mod and is not used.
- **FX helper**: `fx_apply.py` currently lives in `tools/pasqal_lab/`. The studio carries its own copy
  (`tools/studio/server/studio_server/fx_apply.py`) that imports `tools/fx_lab/batch.py`, so slice 1 does not depend
  on a tool it replaces.
- **Model backend**: unchanged process (`live_backend.py`), already supports design and clone requests with a seed.
  It stays separate so the app starts with the GPU free and the model loads only when wanted.
- **Ports**: Studio on 8930 (new); the old pages keep theirs until retired.

### 5.1 API sketch

| Route | Purpose |
|---|---|
| `GET /api/speakers`, `GET /api/speakers/:slug` | list with status; detail (origin, catalog clips, lines, candidates, profile) |
| `POST /api/speakers/:slug/profile`, `POST …/active` | save profile; copy to canonical location |
| `GET /api/speakers/:slug/lines`, `…/takes`, `…/profile` | lines with annotation and bank clip path; takes newest first; saved profile |
| `POST /api/speakers/:slug/design/{generate,keep,order,verdict,description}`, `…/register` | live design, candidate state, register the pick into the prompt bank |
| `POST /api/speakers/:slug/clone/generate` | clone one line with options (proxies to backend, records a take) |
| `POST /api/speakers/:slug/takes/:id/fx`, `…/rate` | apply FX preset(s) to a take; rating/notes |
| `GET /api/fx/presets` | preset names (writing `assignments.json` is a later slice) |
| `GET/POST /api/pools`, `…/assignments` | pool slots and line assignments |
| `GET/POST /api/matches`, `/api/qa` | reviews |
| `GET /api/model/health` | `down/ready/busy` ("loading" is reported as `down`: the backend listens only after the model loads) |
| `GET /file?p=` | audio from whitelisted roots |

## 6. Frontend structure

Vue 3 with TypeScript and Vite is a decision, not an inherited convention: the repo has no Node toolchain today (its
pages are single-file vanilla HTML with stdlib servers). The reasons are that this app is far larger than any existing
page, that shared components (`ClipCompare`, the ranker, a per-speaker context) are reused across five sections, and that
the project owner builds web UIs in Vue. The costs are a second dependency universe (Node, `npm install`, a build or dev
server) and that the structural rules below are set by this project (thin views, reusable components, composables own
state and side effects, typed `InjectionKey` context for subtrees, no magic numbers, files under 500 lines). A no-build
Vue-from-CDN page was considered and rejected because it gives up TypeScript and single-file components.

```
src/
  views/            SpeakersView, SpeakerView, PoolsView, FxView, MatchesView, QaView   (thin)
  components/
    shared/         AppShell, ModelStatus, ClipCompare, AudioPlayerBar, StarRating, SectionCard, EmptyState
    source/         SourcePanel, RealClipList, DesignPanel, LiveDesign, CandidateRanker, SuppliedClip
    lines/          LineList, EmotionChips
    options/       ModelOptions
    fx/             FxPicker, FxLabFrame
    results/        TakeRow, ResultsPanel
    pools/          SlotList, AssignmentTable, SpotCheck
  composables/      useAudioPlayer, useGenerate, useDragOrder, useSeedPolicy, useSpeakerContext
  stores/           model (status), speakers, profile (current), takes, fx (presets), pools
  api/              typed client, one module per route group
```

Notes:
- `ClipCompare` takes N labelled clips and plays them with one shared audio element; it is used in Source (real vs.
  clone), Results (real/bank/raw/FX), Render QA and Pools.
- `useSpeakerContext` (provide/inject) gives the Speaker page's sections the profile, selections and actions without
  prop drilling; views stay thin.
- Candidate ranking uses native drag-and-drop with keyboard alternatives (move up/down buttons).
- The FX Lab embed is an iframe of the current Faust page with a `postMessage` bridge limited to: load clip, save preset
  name. A full Vue port is a separate later project (its slot grid and WASM glue are non-trivial).

## 7. First slice (scope fence)

Replace **only** `voice_design/audit.html` (:8907) and `pasqal_lab` (:8910), as the Speakers section, reading existing
files. That covers what the pilot-NPC audition and the Pasqal work need now:
- app shell, model status, audio player, `ClipCompare`
- Speakers list and Speaker page with Source (real, designed with live design and ranking, supplied), Test lines,
  Options, Post-processing (preset picker, FX applied through the existing `fx_apply.py`), Results, profiles

**Milestone M1 (audition usable)**, reached after the Source section: speakers list, real and designed sources, the
candidate ranker and verdicts written to `audit.json`, all working with the model off. The user has never listened to
the 12 pilot designed voices, and that verdict gates the whole voiceless-NPC track, so the build pauses at M1 for a
real audition before the remaining sections (options, post-processing, results) are built.

Not in the first slice: Pools, FX Lab port or authoring bridge (the bridge needs a message listener added to the
existing FX Lab page, which is a change to an old page), Matches, Render QA. Those keep their current ports.
Speakers without a voice description yet (about 287 of the 299 named NPCs: the named-speaker LLM pass has not run) do not
appear in the list; generating those descriptions is a prerequisite outside this spec, and the list will need a
"no description yet" state when they arrive.
Each later slice is a separate spec and plan. Follow-up work that makes the results effective, also out of scope:
`plan.py` reading profiles, wiring `match_decisions.json`, and `batch.py` reading the studio's assignments.

## 8. Testing

- Backend: pytest for pure functions (profile merge, path whitelisting, candidate order/keep), plus API tests
  against a **mock model backend** (no GPU). The mock backend is new work; the existing tests only cover pure functions.
- Frontend: Vitest for stores and composables; component tests for `ClipCompare`, `CandidateRanker` (including keyboard
  reordering), `ModelOptions`; no snapshot-only tests.
- End to end: browser checks (the Playwright MCP tools) against the built app with the mock backend, covering rank,
  keep, generate, apply FX, save profile. The real model is exercised manually when the GPU is free; reproducibility (same seed, same audio on the
  same machine) is verified at that time, not assumed.
- Safety checks: the audit data files are backed up and compared before/after any test that writes.

## 9. Risks and open questions

1. **Pool assignment policy** (T3): automatic with exception queue and spot check, with per-line provenance recorded
   (recommended by both the author and the reviewer), or per-line approval. Awaiting the user's answer. The Pools
   slice is not built in the first slice, so this does not block it.
2. **API framework**: stdlib `ThreadingHTTPServer` chosen for slice 1 (see section 5). The reviewer preferred FastAPI;
   revisit if the route count or validation burden grows.
3. **Seed reproducibility is unverified.** Seeding was added to `design.py` and `live_backend.py` but no run on the
   real model has confirmed that equal seeds give equal audio. Kept candidates always save the WAV, so a failure only
   loses the "regenerate" promise, not the voice.
4. **Existing pilot candidates are not reproducible.** The 12 pilot NPCs were generated before seeds were recorded, so
   only their WAVs exist. The UI marks them; no promise of regeneration is made for them.
5. **GPU availability**: the 5080 is shared; the model backend is started only on request. The UI must treat "model
   down" as a normal state.
6. **Doubly processed sources**: for processed real clips (Pasqal), clone quality may be bounded by the source. The
   app surfaces this (side-by-side compare); it does not solve it. A clean designed base voice is the fallback.
7. **Scope drift**: the old pages stay running until each is replaced; only retire a page after its replacement has
   been used for real work.
8. **Rules**: nothing in the app deletes files; any removal remains a manual, itemized action by the user.
