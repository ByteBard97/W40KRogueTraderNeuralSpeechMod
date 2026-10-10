# Voice Studio redesign: gaps against the current app

Compared: `pages/*.html` and `screens/*.png` against `tools/studio/web/src` and `tools/studio/server/studio_server`.
Read-only analysis; nothing was changed.

Legend for the "Kind" column:

- **FE**: frontend only, derivable from the existing API.
- **API-small**: additive field or query param on an existing route.
- **API-new**: new route or a new server concept.
- **DATA**: needs new stored data (a new key in a JSON file, or a data source that does not exist yet).

## Facts about the current system that drive most gaps

1. **Model calls are synchronous and the browser drives the batch.** `POST /clone/generate` and `/design/generate` block until `live_backend.py` answers (timeout 240 s). `runBatch` loops in the browser, and `ResultsPanel` stops the batch when the page unmounts. There is no server job, no queue, no job id.
2. **The model backend reports only `{ok, busy}`.** There is no step progress and no cancel; the GPU lock cannot be interrupted. `ModelClient.health()` collapses everything to `ready`, `busy` or `down`. The web `model` store also maps a failed fetch of the studio API to `down`.
3. **Audio is a single `Audio()` element** with `play(id)` and no time, seek, speed, loop, queue or metadata.
4. **The shell has no counts and no shortcuts.** Only Render QA binds keys (`useQaKeys`). Confirmations use `window.confirm`; there are no toasts and no undo.
5. **Pick equals rank 1.** `apply_order` sets `pick = order[0]` on every reorder. The design treats pick and rank as separate ("no pick yet" while six candidates are ranked).
6. **Design content versus real data.** The FX mock shows 8 labels (servitor, tech-priest, psyker, ...). The harness data has 6 (`machine`, `vox_channel`, `helmet`, `ethereal`, `monstrous`, `cavernous`); `LABELS` is hard-coded in both `fx_library.py` and `LabelMap.vue`. Mock numbers such as "9 speakers" or "uses 3" have no counterpart. Treat the mock labels as placeholder content.

---

## Shell, topbar, shortcut overlay, persistent player

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| "Speakers 20 left" | Not shown | FE (+ shell store) | Count `status=='needs_voice'` from `/api/speakers`; the list must load at app start, not only on `/speakers`. |
| "Pools 61" | Not shown | FE | `queue_entries` from `/api/pools`; hide the badge on 404 (not built). |
| "Matches 277" counting down as you review | Not shown | API-small | `counts` has no total or reviewed count. See the Matches table (`counts.reviewed`, `counts.total`). |
| "Render QA 11,051" (unjudged) | Not shown | API-small | Only reachable today by calling `/api/qa/clips?limit=1` and reading `stats.unjudged`. |
| One cheap call for all four badges | n/a | **API-new** | `GET /api/summary` -> `{speakers:{total,needs_voice,picked,registered}, pools:{built,queue_entries,queue_lines}|null, matches:{total,reviewed,flagged_unreviewed}, qa:{run,unjudged,good,bad}, model:{...}}`. New module `summary.py` composing `speakers.list_speakers`, `pools.summary`, `matches.rows`, `qa.get_verdicts`. Stores update badges optimistically after each action and re-fetch on route change. |
| Model pill: ready / busy / down with reason | Dot plus word, 5 s poll | FE | Restyle. Distinguish "studio API unreachable" (fetch threw) from "model backend down" (state `down`); the design's down text names `:8930`, which is the studio API. Add Retry (`model.refresh`). |
| Busy pill: "Generating 3 / 6", meter, elapsed; "Designing c6 0:04" | Only "busy" | **API-new** | Needs the server job registry (below). Pill reads `GET /api/jobs?active=1`. |
| Pill click opens job queue with Cancel | n/a | **API-new** | Same job API. |
| Keyboard shortcuts overlay (`?`, Esc), per-page content | None | FE | A per-route shortcut registry feeding one overlay component. |
| Page-level key handling on every page (J K N A R Z S P ...) | QA only | FE | Generalise `useQaKeys` into a registry that ignores INPUT/SELECT/TEXTAREA. |
| Toast stack with Undo (Z), error toast with Retry and "kept locally, will retry" | `window.confirm`, inline error text | FE (+ API for pool undo) | QA already has an optimistic queue with rollback; "kept locally and retry" means holding failed saves in a pending list. Undo for Pools needs server support (see Pools). |
| Persistent bottom player: now-playing title and path, prev/next clip, seek, speed (0.75 to 1.5), loop, volume, auto-play next, ← → seek, `, .` clip, `[ ]` speed | `useAudioPlayer`: play/stop only, no UI | FE | Extend the composable: `title`, `subtitle`, `queue` (list of clips for prev/next), `currentTime`, `duration`, `seek`, `rate`, `loop`, `volume`; persist rate, loop and volume in localStorage. Inline play buttons pass metadata. |
| A/B strip with playhead kept across sources (fraction, with a toggle to absolute seconds) | `ClipCompare`: separate `play()` calls, playhead lost | FE | Swap `src`, restore `currentTime = frac * duration`, keep `playing`. |
| Mini waveform with progress (design-system page only, not used on the six pages) | None | FE (optional) | Decode client-side; if wanted in long lists, `GET /api/peaks?p=<wav>&n=40`, cached, in `qa.py`. |

## Speakers (`speakers.html`)

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| Hero: "43 speakers, 20 need a voice, 23 have a source, 1 picked, 0 registered" | Count and picked | **API-small** | "registered" is not in `/api/speakers`. Add `registered: bool` per speaker: `prompts.json[name][0].event == "designed_<slug>"` (register.py writes exactly that). Optionally `registered_stale` when the pick's file differs. `speakers.list_speakers`. |
| Segmented "Voices done 1/43" bar with registered / picked / in progress / not started | None | **API-small** | "In progress" needs ranking progress. Add per speaker `ranked: n`, `candidates: m` (audit `cands[*].fit` count over manifest candidates) and `pick: "c2.wav"|null` (replace or supplement `has_pick`). The audit file is already read in `list_speakers`. |
| Per-row "4 / 6 ranked", "picked c2", "not started" | Only "✓ picked" | **API-small** | Same fields as above. |
| Rows grouped: "Needs a voice" (named plus slots), sub-head "Shared slot voices", "Has a source", "Profile saved" | Groups by status only | **API-small** | Add `kind: "named"|"slot"|"real"` (slot = manifest `role == "pool slot"` / `pool_` prefix). Everything else is layout. |
| Slot rows show lines, and the sub-head says "used by 6,717 unnamed lines" | `line_count` is 0 for slots (counted by speaker name in jobs) | FE | Join `/api/pools` `slots[].lines` on `speaker_key`/`slug`; total from `summary.total`. The mock shows 0 lines per slot, which is wrong against real data. |
| Row status text: "source set" / "no lines" for real speakers | None | FE | `line_count == 0`. |
| Filter `/`, All / Unfinished / Done, J K Enter, N next unfinished | Text filter only | FE | |
| "Continue: Governor Ruoldo [N]" | None | FE | First in-progress, else first unstarted, from the list fields above. |
| Space plays the focused row | None | **API-small** | Needs a sample clip per row: `sample` = pick's wav, else rank-1 curated clip (`speakers._clips`). Adds one path per speaker to the list. |
| Register all: inline confirm "Register 1 pick ... Speakers without a pick are skipped (42)"; result "Registered 1 · Calligos Winterscale → c2 · skipped 42", with skipped broken into "designed, no pick yet (19)" and "real voice, nothing to register (23)" | `window.confirm`; result lists names plus failures only | **API-small** | `register_all` should return `registered: [{name, cand}]` and `skipped: [{name, reason: "no_pick"|"real"|"error", detail}]`. The two skipped groups are FE-derivable from the list but the "→ c2" is not, since the pick is a bool today (fixed by `pick`). `design.register_all`. |
| "Profile saved" empty state copy | Group hidden when empty | FE | |

## Speaker workbench (`speaker-workbench.html`)

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| Sticky subbar: Prev `[` / Next `]`, "Speaker 8 / 43", "1 picked", profile saved text, Save `S`, Set active, Register {pick} `P` | Prev/next, position, picked count, Register all in `SpeakerNav` | FE | Keys and layout only. |
| Source-type tabs: Designed / Catalogue clips / Supplied wav | All three stacked | FE | |
| "Supplied wav" as a real input | Free-text repo path (`SuppliedClip`) | API-new (optional) | A file upload: `POST /api/speakers/{slug}/supplied` (base64 or multipart, body `{name, wav_b64, text}`) writing `data/studio/<slug>/supplied/`; module `store.py`. Only needed if the design means upload rather than path. |
| "6 candidates · 2 / 6 scored · no pick yet" | Not shown | FE | Count candidates with `verdict.fit`. |
| Compare on: Design sample / Test 1 / Test 2, keys 1–6 switch candidate | Clone tests listed per candidate; no compare strip | FE | `design.clones[]` already holds `candidate`, `text`, `file`. Test labels derived from the text. |
| Ranking row: drag, rank, p_us, top, "no seed", Up/Down, Reject / "Undo reject", dimmed rejected row | Mostly present | FE | Dim and strike rejected rows; keyboard Alt+↑↓, R, 1–5, B/A/O. |
| **Accent score** 1–5 stars separate from **Fit** 1–5 | Only `accent` (category) and `fit` | **DATA + API-small** | New key `accent_score` per candidate in `audit.json` `cands[c]`. `design.post_verdict` passes the body to `audit_server.apply_verdict`, which ignores unknown keys, so the studio must handle `accent_score` itself in `design.py` (do not edit the shared helper) and add it to `Verdict` in `types.ts`. Returned by `speakers._design` automatically if stored in `cands[c]`. |
| Explicit **Pick / Picked** per candidate, independent of rank; "no pick yet" | Pick = rank 1; `design/verdict` accepts `pick` but reorder overwrites it | **API-small** | `design.post_order` should not reset `pick`. Proposal: body `{order, follow_rank?: bool}`; when false, leave `audit[name].pick` alone (or clear it only if the picked candidate left the list). Decide product intent first: design implies pick is explicit. |
| "Render 2 clone tests" for candidates with none | Clone tests only come from offline `clone_test.py` output (`clone_manifest.json`) | **API-new** | `POST /api/speakers/{slug}/design/clone-tests` body `{cand, lines?: [guid]}` -> job (see below) that clones the candidate onto two chosen real lines via `model.call`, writes `data/voice_design/clones/...` and a `clone_manifest.json` entry. New results will be unscored (`scores` null) because accent scoring is an offline step. New module `clone_tests.py`. |
| In-list job row: "c6 · Designing from the description · seed 4821 · cfg 2 · 10 steps · 0:04 elapsed · Cancel", skeleton bar | Button text "generating…" in a separate box | **API-new** | Server job (below). The seed must be known before the call finishes: `design.generate` should draw the seed itself (`random.SystemRandom().randrange(2**31)`) when blank and pass it to the backend, and return it in the job record. |
| Live design disclosure; "Keep as c7" | Present (seed/cfg/steps, Keep) | FE | Label with the next candidate id: `max(cN)+1`. |
| Test lines: "6 of 79 ticked · neutral 2, amused 2 ...", emotion chips with counts and "+4" | Chips without counts; no per-emotion tally | FE | |
| Line shows duration of the bank render ("7.9 s") | `Line` has no duration | **API-small** | Add `dur` to `speakers.speaker_lines` by reading the wav header (`qa._duration`), cached by mtime. |
| "Showing 1–8 of 79" with a progress bar, Show all | Cap 200 with "show more" | FE | |
| Options: seed policy "New seed per line / One seed for all / Fixed…" | Blank or typed seed only | FE | "One seed for all" = draw one random seed client-side before the batch. Also a one-line options summary. |
| Post-processing: numbered chain chips with ×, grouped searchable "Add" select (40 presets by family: Machine, Vox and helmet, Ethereal, Space, Vocoder), version tags v1..v4 | Flat button list in pick order | **API-small** | Presets have no `family` or `version`. Add both to `fx_library.library()`: version from a `vN` prefix (default `v1`), family from the text before `:` (or a `family` key in `scenarios.json` / `presets.json` to override). A regex in FE would work but is fragile ("Phaser test", "Helmet + vox"). |
| Results header "source c2 · 6 lines · 2 FX", Generate `⌘↵`, "~45 s on the current model" | Button with count | FE | Estimate = mean of past `Take.seconds` x takes. |
| "Runs in the background; keep ranking"; per-take card "Take 3 of 6 · text · 0:06" with progress bar; "3 more queued · Cancel all" | Browser loop; leaving the page stops it | **API-new** | Server job queue, see proposal 1. Percent bar is an elapsed/expected estimate unless the backend ever reports steps. |
| Per-line A/B: Real / Bank / Clone / +FX with durations | `ClipCompare` has source, bank, raw, fx without durations | **API-small** | Bank duration comes from `Line.dur` (above). Clone has `audio_s`. FX duration is not stored: record `dur` in `take.fx` in `fx.apply_to_take`. "Real" is disabled in every mock case; there is no real-voiced counterpart of an unvoiced line in the data, so keep it a disabled slot. |
| Rating stars with "Saved" indicator, keys 1–5 | Stars, no indicator | FE | |

## Pools (`pools.html`)

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| Header: routed total, built time, threshold; "Decisions saved"; Rebuild | Present as text | FE | |
| Tile "61 entries · 249 lines below 0.8" | `queue_entries`, `queue_lines` | FE | |
| Tile "N / 8 slots spot-checked" and "Next unchecked slot" | `slots[].spot.checked` | FE | Define "checked" (suggest `checked >= 10` and `wrong == 0`, or `checked > 0`). |
| Tile "0 per-line overrides" | Not exposed | **API-small** | `summary()` add `overrides` = count of routes with `source == "override"`. |
| Route bar; click a segment to filter the routes table | Summary rows only | **API-small** | Segments for slot, narrator and speaker are filterable today (`to=`), but bank vs no-bank is not. Add `bank=1|0` to `routes_page`. |
| Review queue as a focus list: "1 of 61", progress bar, J K, A accept, M move, S skip | Paged list with buttons | FE | Cursor state in the store. |
| Entry header: reason chips, "guess: male · human · unknown role" | `reasons`, `attr` | **API-small** | `role` is missing from `queue()` entries (roster `x.role`). |
| Play button on each sample line | Samples are plain strings | **API-small** | Change `queue()` `samples` to `[{guid, text, wav}]` (wav from `_export_index`, `data/render/export/<wav>`; null if the line is not rendered), or add `sample_items` to stay compatible. Same for `spot_check_sample` items and `routes_page` rows (`wav`). |
| "Move to" including **"New designed voice…"** | Only existing slots, game voice, narrator | **API-new + DATA** | `POST /api/pools/slots` body `{name, gender, species, age?}` creates a slot record in `pools.json` and a manifest entry via `ensure_slot_speakers`. A hand-made slot must survive `rebuild` (it does if at least one override route points at it, via the `prev_slots` recovery; otherwise store it under `custom_slots` and merge it back). `pools.py`. |
| Skip `S` | No equivalent | FE | Session-level defer, no persistence needed. |
| **Undo toast (Z)** after Accept, Move, Merge | None | **API-new** | `override()` should return `{changed, undo: {previous: {guid: route}}}` and a new `POST /api/pools/routes/restore` body `{previous}` writes them back (a few hundred routes at most). Merge: store the moved guids and the removed slot record under `merged[src]` (today it is just `src -> dst`), then `POST /api/pools/slots/{slot}/unmerge`. Both in `pools.py`. |
| Slots list: dot for spot-checked, lines, Spot check / Re-check, Merge with inline confirm "N lines move; the slot and its name are removed" | Present (plus rename) | FE | Restyle. |
| Spot check panel: 10 lines, play buttons, Right / Wrong, "4 / 10 marked", keys Y W J, Submit disabled until done, "1 wrong so far" | Present without audio or keys | **API-small** | Add `wav` to sample items. Note `size` doubles to 20 after a wrong answer; the "/ 10" must use `size`. |
| Routes table: Roster entry column, Destination "Slot · Male human / Speaker · Idira (bank) / Named · X / Narrator", Conf., search box, Confidence filter ("Below 0.8"), override select, play button | Text, destination, confidence, move-to-slot only | **API-small** | `routes_page` add: `q` (text or roster name), `conf_lt`, `entry_name`/`entry_label` per row (roster index as in `queue()`), `wav` per row, and a `bank` flag. Override select can also offer narrator (API already supports it). |
| Page size 50, "1–50 of 6,717" | 25 per page | FE | |

## FX (`fx.html`)

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| "40 presets · 8 labels"; preset library grouped by family with version tags, search | Flat list with `source`, `notes` | API-small | Family and version, as in the workbench table. Label count: see fact 6. |
| Preview play button on every preset | None | **API-new** | `GET /fx-render?preset=<name>&p=<repo wav>` (or `presets=a\|b`), same shape as `/fx-file`: runs `fx_apply.py` in `.venv-fx`, caches on (path, presets, mtime). Default sample wav = a Pasqal clip. Player "Raw / With FX" bypass uses the original file as the other side. |
| Label to chain map with drag-reorder, "+ Add", per-label "Speakers" count, state dot (edited / matches file) | Chain with ←/→ buttons, add select, Save | FE + API-small | Dirty state and counts of edits are FE (compare draft with saved; `LabelMap` already snapshots). "Uses" needs `GET /api/fx/labels` or `assignments/preview` to include `usage: {label: {lines, speakers}}` (count from the roster lines in `fx_library.expand`; speakers via pool routes). |
| Header "N unsaved changes", Discard, "Map matches the file on disk", `⌘S` | None | FE | |
| "Write map…" with inline confirm: "Write N changes to X? The current file is kept as X.<timestamp>.bak.json. Changes reach 9 speakers" | Two steps: "Save label map" (writes `data/studio/fx_labels.json`, no backup) and Preview then "Write assignments.json" (one `.bak`, overwritten each time) | **API-small** | Decide what "Write map" writes. Proposal: keep both files, but timestamp the backups (`assignments.<ts>.bak.json`, and a backup of `fx_labels.json` on save) in `fx_library.write` / `save_labels`; return `backup` and `affected_speakers` from write. |
| "Restore backup" on the success toast | None | **API-new** | `GET /api/fx/backups` and `POST /api/fx/restore {backup}`; module `fx_library.py`. |
| Assignments preview table: Speaker / Label / Now / After write / A/B, changed rows first | Counts plus 5 guid -> presets lines | **API-new** | `GET /api/fx/assignments/diff` -> `{rows:[{speaker, labels:[...], lines, now:[presets], after:[presets], changed, sample_wav}], file_mtime}`. "Now" = read current `assignments.json`; "After" = `expand()`. Caveat: labels are per roster line, speakers get presets from `active.json`; group by pool destination (slot or speaker) to get one row per voice. A/B uses `/fx-render` with the two chains. |
| FX Lab frame: Source select ("Pasqal (845)"), "Start from" preset select, status pill "not reachable on :8908", Retry, Copy command, Collapse | Bare iframe; clip hand-over via `postMessage` | FE + FX Lab | Pill and Retry are FE (probe the port). Source select is FE (fetch a clip and `sendClip`). "Start from preset" needs a new message handled inside `tools/fx_lab` (e.g. `studio:load-preset`); not a studio-server change. |

## Matches (`matches.html`)

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| Progress "Reviewed N / 277", accepted and rejected split | `counts`: flagged, bank, nobank, undecided | **API-small** | Add to `counts`: `total`, `accepted`, `rejected`, `reviewed` (explicit decisions only), `flagged_unreviewed`. Semantic conflict: the server treats clean matches as auto-accepted (`effective`); the design makes you review all 277. Pick one; with the design's model `state=unreviewed` (decision empty) is needed in addition to `undecided`. |
| Group tabs Flagged 25 / Has bank 118 / No bank 134 / All 277 | `counts` give the three; All = sum | FE | |
| Master/detail layout: queue with dot, "name → speaker", "suggest accept / Accepted / Rejected", `src · N lines` | Flat list of full rows | FE | |
| **"Suggested: Accept/Reject"** | Not computed | **API-small** | Add `suggest: "accept"|"reject"` (+ `suggest_reason`) in `matches.rows`. Candidate rule: reject when `warning` reports a game-gender mismatch with few lines; accept when the match is exact or `ambiguous_with` only lists homonyms. Needs the owner to approve the rule. |
| "Why flagged" text | `warning`, `ambiguous_with` | FE | Compose "Also matches X. Accepting uses the X bank." from `ambiguous_with` and `has_bank`. |
| "Hear {speaker}" (Space) plays the proposed speaker's bank sample | None | **API-small** | `speaker_sample` per row: first `prompts.json[speaker]` clip (`data/voices/<wav>`), banked speakers only. |
| Keys J K A R N Z, auto-advance after deciding, "k of 25" | None | FE | |
| Undo toast | None | FE | `decide(id, previous)` already supported; the store keeps `confirmed`. |
| Decision select "Not reviewed / Accepted / Rejected / Any", Speaker field, search `/` | Present with different semantics | API-small | See `state=unreviewed` above. |
| Performance | `matches.page` recomputes `rows()` on every request and each decision triggers a full `pools.rebuild` | API-small | Not a design gap, but rapid A/R review will hit it: cache `rows()` by (roster, decisions) mtime, and let `save` accept `rebuild: false` / debounce the rebuild. |

## Render QA (`render-qa.html`)

| Design shows | Today | Kind | Notes / proposal |
|---|---|---|---|
| Run select, search `/`, Sort (6), Compressor Off/Mild/Strong plus `X` | Present | FE | Restyle. |
| "Filters 0 active" popover (speaker, reference, engine, flag, verdict) | Always-visible selects | FE | Count non-default values. |
| "N good · N bad · N unjudged" and a "this view" bar | Run-wide counts only | **API-small** | `stats` is computed over the whole run, not the filtered set. Add `view: {good, bad, unjudged, total}` in `qa.page`. |
| "this session N judged" | None | FE | Counter of first-time verdicts since page load. |
| "Per reference" panel | `stats.by_ref` rendered as text | FE | |
| "clip 2 of 11,051", queue "1–40 of 11,051 · Load 40 more" appending | Paged replace, Prev/Next | FE | Use the existing `exclude` mechanism to append. |
| "Next unjudged" `N` across the whole queue | Only searches the loaded 40 | FE (or API-small) | Auto-load more until one is found; or `GET /api/qa/next?<filters>&after=<guid>` returning `{index, guid}` if loading is too slow. |
| Flag chips with the reason text ("below 3.5 chars/s", "hit the 30 s length cap") | Flag names only | FE | Dictionary (the mock's `F` table), or a `flag_info` map in `qa.facets`. Thresholds live in `qa.py`, so server is the safer source. |
| "Sent to the model as" | `context` | FE | Present for the export run. |
| ASR box "heard ... · word error rate" | `heard`, `wer` exist | **DATA** | Only filled for per-run folders with `asr.jsonl`. The merged export (the 11,051) has none. Needs the ASR output merged into the export (from `tools/render_corpus/asr_check.py`) or a second source path in `_export_clips`. |
| A/B slots: Clip / Clone reference / Earlier render / Real line (keys A S D F) | Slots exist | FE (+ DATA) | `old` and `real` are empty for the merged export, so D and F are always disabled there. Real lines exist only in a run's `real.json`; wiring them into the export needs data. |
| Tag chips with keys 1–9, 0; "Tags also mark the clip bad" | Chips, tags mark bad, no keys | FE | `QA_TAGS` already has exactly 10 entries. |
| Note, "Enter saves" | Saves on change/blur | FE | Add explicit Enter handler. |
| "Saved · good / Unjudged" status, error toast "not saved ... kept locally, will retry" | Optimistic with rollback, error text | FE | Retry list instead of rollback. |
| Player: prev/next, 1× / 1.25× / 1.5×, Auto-play next | None | FE | Shared player. |

---

## Proposals in detail

### 1. Server job queue (biggest item)

New module `studio_server/jobs.py` with one worker thread (the GPU takes one generation at a time anyway) and an in-memory registry persisted to `data/studio/_jobs.json` so a restart does not lose history.

- `POST /api/jobs` body `{kind: "clone"|"design"|"clone_test", slug, items: [<existing /clone/generate or /design/generate bodies>], fx?: [preset names]}` -> `{id}`. Reuses `clone.generate` / `design.generate` per item inside the worker, and applies `fx.apply_to_take` after each clone take as `ResultsPanel` does now.
- `GET /api/jobs?active=1&slug=` -> `[{id, kind, slug, state: "queued"|"running"|"done"|"failed"|"cancelled", index, total, current: {text, seed, cfg, timesteps, started_at, elapsed_s, expected_s}, takes: [take ids], error}]`. `expected_s` = mean of past `Take.seconds` (no step progress exists). Poll every 1 s while any job is active; add `job: {id, label, index, total, elapsed_s}` to `/api/model/health` so the topbar pill needs one call.
- `POST /api/jobs/{id}/cancel`: marks remaining items cancelled and drops the in-flight result. The backend cannot abort a running generation, so say that in the UI ("finishes the current take").
- Keep the synchronous routes for tests and the mock stack.
- Frontend: `ResultsPanel` and `DesignPanel` submit a job and read results from takes/jobs; `liveTakes` entries come from the job result.

### 2. Shell summary and shared player (frontend plus `GET /api/summary`)

See the shell table. Without it the topbar needs four loads on every page.

### 3. Speakers list fields

One change to `speakers.list_speakers`: add `kind`, `pick`, `ranked`, `candidates`, `registered`, `sample`. Unblocks the hero progress bar, per-row "4 / 6 ranked", registered state, Space-to-play, slot grouping.

### 4. Pool undo and "New designed voice"

Restore payload from `override`, `unmerge`, `POST /api/pools/slots`.

### 5. FX diff, backups, preset preview render

`/api/fx/assignments/diff`, timestamped backups plus `/api/fx/restore`, `/fx-render`, family/version fields.

### 6. Pick separate from rank, `accent_score`

`design.post_order(follow_rank)`, `accent_score` in verdict handling.

---

## Ranked list of server changes

1. **Job queue and job-aware health** (`jobs.py`, `/api/jobs*`, `model.py`/`routes.py`). Unblocks: topbar busy pill with take n of m and elapsed, the generation job card with Cancel, "runs in the background", queued takes, generation surviving page changes, in-list "Designing c6" row. Largest piece of work; also fix the seed-before-call detail in `design.generate`.
2. **Shell summary** `GET /api/summary` (`summary.py`). One call for the four topbar counts plus model state.
3. **Speakers list enrichment** (`speakers.list_speakers`): `kind`, `pick`, `ranked`/`candidates`, `registered`, `sample`; and `register_all` result shape (`{name, cand}`, categorised skips).
4. **Pools: undo, new slot, audio and search** (`pools.py`): restore payload and `routes/restore`, `unmerge` (store moved guids), `POST /slots`, `overrides` in summary, `role` in queue, `wav` on samples and route rows, `entry_name`/`q`/`conf_lt`/`bank` on `routes_page`.
5. **Matches: counts and suggestion** (`matches.py`): `counts.total/accepted/rejected/reviewed/flagged_unreviewed`, `state=unreviewed`, `suggest` + reason, `speaker_sample`; cache `rows()` and defer rebuild.
6. **Pick independent of rank and `accent_score`** (`design.py`; data key in `audit.json`).
7. **FX: diff preview, timestamped backups plus restore, `/fx-render` preset preview, `family`/`version`, per-label usage** (`fx_library.py`, `fx.py`, `app.py`).
8. **Clone tests from the UI** (`clone_tests.py`, runs on the job queue from item 1).
9. **QA: `view` stats** in `qa.page`, flag reason dictionary in facets; **ASR and real-line data for the merged export** (data work in `tools/render_corpus`, then `_export_clips`).
10. **Small additions**: `Line.dur` (`speakers.speaker_lines`), `dur` in `take.fx`, optional supplied-wav upload.

Everything not listed above is frontend work: shortcut registry and overlay, toasts, the shared player (seek, speed, loop, queue, playhead-preserving A/B), restyled panels, keyboard handling on every page, filters popover, session counter, dirty tracking on the FX map, line and emotion tallies.
