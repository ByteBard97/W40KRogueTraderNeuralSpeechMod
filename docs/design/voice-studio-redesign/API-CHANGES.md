
## Pools

All under `/api/pools`. Module `studio_server/pools.py`; routes registered in `routes.py`. Paths in `wav` fields are repo-relative (`data/render/export/<wav>`), servable via `/file?p=...`; `null` when the line has no render.

### Changed responses

- `GET /api/pools`: new `overrides` (number of routes with `source == "override"`). Slots may carry `custom: true`.
- `POST /api/pools/routes` (override): now `{changed, undo: {previous: {guid: route}}}`. `previous` holds each touched line's full route before the change; post it to `/routes/restore` to undo Accept and Move.
- `GET /api/pools/queue`: each entry gains `role` (roster role or null) and `sample_items: [{guid, text, wav}]`. `samples` stays a list of strings (same order, same lines), so existing UI keeps working.
- `GET /api/pools/spot-check/{slot}`: items are `{guid, text, entry, wav}`. `size` is 10, or 20 after a wrong answer: show "n / size".
- `GET /api/pools/routes` rows: new `entry_name`, `entry_label` (roster entry of the line, null without one) and `wav`.

### New query params on `GET /api/pools/routes`

All combine with the existing `to`, `slot`, `speaker`, `queued`, `offset`, `limit`.

- `q`: case-insensitive substring over line text, roster name, roster label and routed speaker.
- `conf_lt`: number; keeps lines whose confidence is set and below it ("Below 0.8"). A non-number is 400.
- `bank`: `1` keeps lines routed to a named speaker with a prompt bank, `0` named speakers without one. Both exclude slot and narrator lines.
- `entry_name`: case-insensitive substring of the roster entry name or label.

### New routes

- `POST /api/pools/routes/restore` body `{previous: {guid: route}}` -> `{changed}`. Writes the routes back exactly. All or nothing: 400 if `previous` is empty, a guid is unknown, `to` is invalid, or a slot route points at a slot that no longer exists (unmerge first). Restoring an auto route puts it back in the review queue.
- `POST /api/pools/slots/{slot}/unmerge` -> `{changed, slot}`. Brings the merged-away slot back, moves home the lines recorded at merge time that are still in the target (lines overridden elsewhere since stay put), and removes the rename entry so rebuilds stop merging it. 404 when there is no recorded merge (including merges made before this change). Chained merges unmerge in any order.
- `POST /api/pools/slots` body `{name, gender: "male"|"female"|"any", species?: "human", age?, description?}` -> the slot record `{id, name, speaker_key, gender, species, age, lines: 0, custom: true, slug, spot}`. Id is `custom_<slugified name>`, speaker key `pool_<id>`. Creates the `design_manifest.json` entry through `ensure_slot_speakers` (existing entries are never touched), so it shows up under Speakers as a designed speaker. The slot is stored in `custom_slots` in `pools.json`, so it survives `rebuild` even with zero lines. 400 on empty name or bad gender; 409 when the id or manifest name is taken.

### Storage notes

`pools.json` gains `custom_slots` and `merge_undo[src] = {into, guids, slot, repointed}`; `merged` keeps its `src -> dst` shape, so a merge is still re-applied as a slot rename on every rebuild. Old files without the new keys load fine.

## Matches

Module `studio_server/matches.py`. Review model: the design reviews all rows, so use `decision` (explicit, `""` when never reviewed), not `effective` (which counts clean matches as auto-accepted and stays for the old filters).

### Changed responses

- `GET /api/matches`: `counts` keeps `flagged`, `bank`, `nobank`, `undecided` and gains `total`, `accepted`, `rejected`, `reviewed` (accepted + rejected, explicit decisions only), `unreviewed`, `flagged_unreviewed`. Counts ignore every filter. The response also has `pools_stale: bool` (a deferred pools rebuild is pending).
- Row fields added: `suggest` (`"accept"|"reject"`), `suggest_reason` (text or `""`), `speaker_sample` (repo path of the banked speaker's first prompt clip, servable via `/file?p=`; `null` without a bank or clip). Rule for `suggest`: `reject` when the match has a `warning` (the text contradicts the game's gender tag on few lines), otherwise `accept`; `suggest_reason` is the warning text, or "Also matches X, Y. Accepting uses the Z bank." for homonyms. The owner has not approved this rule; it is one function, `matches.suggestion`.
- `state` filter: new `unreviewed` (decision empty), `reviewed` (decision set). Existing `undecided`, `accept`, `reject` still filter on `effective`. Any other value is 400.
- `POST /api/matches/decision` body `{id, value, rebuild?}`. `rebuild` defaults to true (old behaviour, pools rebuilt in the request). `rebuild: false` writes the decision only and returns `{pools_rebuilt: false, pools_stale: true}`; the rebuild then runs by itself 3 s after the last such decision (`REBUILD_DEBOUNCE_S`), or earlier on `POST /api/matches/rebuild`, or before the next `GET /api/pools*` (those handlers flush first, wrapped in `routes.fresh_pools`). If pools were never built the result is `{pools_rebuilt: false}`.
- The review UI should send `rebuild: false` on every click and call `POST /api/matches/rebuild` when leaving the page.

### New routes

- `POST /api/matches/rebuild` -> `{pools_rebuilt: false, pools_stale: false}` when nothing is pending, else `{pools_rebuilt: true, pools_stale: false, queue_entries}`.

### Performance

`matches.rows()` is cached per repo on the mtimes of the roster, conversations, prompt bank and `render/jobs.jsonl`; a decision changes none of them. Callers must not mutate the returned rows. Stale means `match_decisions.json` is newer than `pools.json`.

## FX

Modules `fx_library.py`, `fx.py`; `/fx-render` is in `app.py` next to `/fx-file`.

### Changed responses

- `GET /api/fx/library`: each preset gains `family` and `version`. Version is a leading `vN ` in the name, else `v1`. Family is the text before `:`, else the text before ` +` or ` (`, so `v2 Machine: servitor` is `Machine` / `v2`, `Helmet + vox (...)` is `Helmet`, `Phaser test: ...` is `Phaser test`. A `family` or `version` key on the scenario/preset overrides. Note the real families are not unified (`Vox channel` vs `Vox`); add `family` keys in `scenarios.json` if the design's grouping needs it.
- `POST /api/fx/assignments`: now returns `{path, lines, speakers, backup, affected_speakers}`. `backup` is the file name of the previous `assignments.json` copied to `data/fx_lab/assignments.<YYYY-MM-DDTHH-MM-SS>.bak.json` (`-2`, `-3` on same-second collisions), `null` on the first write. The old single `assignments.json.bak` is no longer written. `affected_speakers` is the number of changed rows in `/assignments/diff`.
- `POST /api/fx/labels` still returns the label map. When the stored map changes, the previous `data/studio/fx_labels.json` is copied to `fx_labels.<ts>.bak.json` first.

### New routes

- `GET /api/fx/assignments/diff` -> `{rows, changed, unmapped_labels, file_mtime}`. One row per voice (pool slot, named speaker, narrator; `entry:<conv>|<id>` before pools are built) plus one per speaker profile: `{voice, kind: "slot"|"speaker"|"narrator"|"entry"|"profile", speaker, labels, lines, now, after, changed, changed_lines, sample_wav}`. `now` is the current `assignments.json`, `after` is what Write would produce; both are the chain most lines of that voice carry (lines without FX do not vote), `changed_lines` counts lines whose chain differs. `sample_wav` is a rendered export clip of the voice or null. Changed rows first, then by line count. `file_mtime` is `st_mtime_ns` of `assignments.json` or null. For the A/B column call `/fx-render` with `now` and `after`.
- `GET /api/fx/labels/usage` -> `{labels: {label: {lines, speakers, presets}}, pools_built}`. `lines` is unnamed lines carrying the label, `speakers` the distinct voices they route to, `presets` the chain length in the map. Before pools exist, voices are roster entries.
- `GET /api/fx/backups` -> `[{name, kind: "assignments"|"labels", path, mtime, size}]`, newest first.
- `POST /api/fx/restore` body `{backup: <name>}` -> `{restored, kind, path, backup}`. Copies the backup over the live file; the file it replaces is backed up first (`backup`), so a restore is undoable. 404 for unknown or path-like names.
- `GET /fx-render?presets=A|B&p=<repo wav>` (or `preset=A`) -> `audio/wav` with the chain applied through `fx_apply.py` in `tools/fx_lab/.venv-fx`. `|` separates presets. `p` is optional: blank uses the first Pasqal prompt clip. Cached on (file, mtime, chain), 32 entries. 400 for an empty or unknown preset, 404 for a missing wav, 501 with "tools/fx_lab/.venv-fx is missing: ..." when the FX environment is absent. Errors are plain text, like `/fx-file`. Raw side of "Raw / With FX" is the original `/file?p=` URL.

## Render QA

Module `qa.py`.

### Changed responses

- `GET /api/qa/clips`: new `view: {good, bad, unjudged, total}`, counted over the clips matching the current filters (speaker, ref, engine, flag, verdict, q) and independent of `offset`, `limit` and `exclude`, so it does not move while "Load 40 more" appends. `stats` stays run-wide and gains `total` and `judged` (good + bad); these are the session-independent counts. "This session N judged" is not server data: count first-time verdicts in the browser.
- `GET /api/qa/facets`: new `flag_info: {flag: "reason"}` for the automatic flags (`cap_hit`, `slow`, `fast`, `short`, `very_long`), built from the thresholds in `qa.py`. Flags set by a render or ASR (`asr_warn` ...) are not in it; show the bare name.
- The merged export now reads `data/render/export/asr.jsonl` (rows `{guid, heard, wer, flags}`) when it exists, same as per-run folders; its mtime is part of the clip cache key.

### Missing data for the merged export (not invented)

- ASR: no `export/asr.jsonl` exists, so `heard` is `""` and `wer` is `null` for the 11,051 clips. Produce it by running a Whisper pass over the export (`tools/render_corpus/asr_check.py` writes `data/render/<run>/asr.jsonl` per run; it needs a run of this kind for `export`, or the per-run files merged into `export/asr.jsonl`). No code change is needed once the file exists.
- Real lines: only a run's `real.json` holds the game's own voiced counterpart; the export has none, so `real` is `[]` and the F key stays disabled there. Needs a merged `export/real.json` (same shape as in the run folders) and a loader in `_export_clips`, not written because the data does not exist.
- Earlier render (`old`): per-run only (it points at `export/wav/<guid>.wav`); `null` for export clips by definition.
- "Next unjudged across the whole queue" is still frontend (load more until found); no `/api/qa/next` was added.

## Core: summary, speakers, picks, jobs

Server modules: `summary.py` (new), `jobs.py` (new), `speakers.py`, `design.py`, `fx.py`, `routes.py`. Tests: `tools/studio/server/tests/test_core_api.py`. All times are Unix seconds (float) except `elapsed_s` / `expected_s` / `dur` (seconds).

### GET /api/summary

One call for the shell badges. Every section except `speakers` is `null` when its data is not built or fails to load (never an error).

```
{ speakers_left: int,                       // speakers.needs_voice, the "Speakers 20 left" badge
  speakers: { total, needs_voice, picked, registered },   // picked = designed speakers with a pick
  pools:    { built, total, queue_entries, queue_lines } | null,   // null = pools not built yet (404 from /api/pools)
  matches:  { total, flagged, flagged_unreviewed, reviewed, accepted, rejected, undecided } | null,
  qa_clips: { run: "export", total, good, bad, unjudged } | null,
  model:    { state: "ready"|"busy"|"down", job?: <job entry, see health> } }
```

`matches.reviewed` counts explicit decisions only; `undecided` is the server's `effective == ""` (flagged and not decided). `matches` and `qa_clips` are cached on the mtimes of their inputs. `model.state` makes one health call to the backend (3 s timeout; instant when it is down).

### GET /api/speakers: new fields per speaker

Existing fields unchanged (`slug, name, origin, line_count, status, has_pick`). Added (also present in `GET /api/speakers/{slug}` under `summary`):

| field | type | meaning |
|---|---|---|
| `kind` | `"named"` / `"slot"` / `"real"` | `real` = game voice; `slot` = designed with manifest `role == "pool slot"` or name starting `pool_`; `named` = other designed |
| `pick` | string or null | the picked candidate id (`"c2.wav"`), same value `design.pick` carries |
| `ranked` | int | candidates that have a `fit` rating in audit.json (the "4 / 6 ranked" numerator). 0 for real speakers |
| `candidates` | int | candidates in the design manifest. 0 for real speakers |
| `registered` | bool | `prompts.json[name][0].event == "designed_<manifest slug>"` (what register.py writes). Always false for real speakers |
| `sample` | string or null | repo-relative wav to play for the row. Designed: the pick, else rank 1 of `order`, else the first candidate (`data/voice_design/clips/<slug>/<cand>`). Real: the rank-1 curated clip as the clip list resolves it, else the first catalogue clip |

### POST /api/speakers/register-all: response shape changed

```
{ registered: [ {name, cand} ],
  skipped:    [ {name, reason: "no_pick"|"real"|"error", detail: string} ] }
```

`skipped` now lists every speaker that was not registered: `no_pick` (designed, nothing picked), `real` (game voice, nothing to register), `error` (a pick failed its checks, for example it is rejected; `detail` is the message). Before, `registered` was a list of names and `skipped` held only failures with `reason` as the message. **The current `RegisterAllButton.vue` / `RegisterAllResult` type must be updated**: it renders `registered` as names and `skipped[].reason` as text (use `detail`).

### Pick independent of rank; accent_score

- `POST /api/speakers/{slug}/design/order` body `{order: [cand...], follow_rank?: bool}`. By default (`follow_rank` absent or false) the pick is **left alone**; it is cleared only if it is not one of the speaker's candidates. `follow_rank: true` restores the old behaviour (rank 1 becomes the pick). The pick is set only through `design/verdict` `{cand, pick: true|false}`. **Behaviour change:** a UI that relied on reorder to set the pick must now send `verdict pick`.
- `POST /api/speakers/{slug}/design/verdict` accepts `accent_score`: whole number 1 to 5, or `null` to clear; anything else is 400. Stored at `audit.json[name].cands[cand].accent_score` and returned in `design.candidates[].verdict.accent_score`. The existing `accent` (category) and `fit` keys are unchanged.

### Durations

- `GET /api/speakers/{slug}/lines`: each line has `dur` (seconds of the bank render, read from the wav header, cached by mtime) or `null` when the line has no render.
- `take.fx` (set by `POST .../takes/{id}/fx`) now has `dur`, the FX wav length in seconds. Existing takes keep their old `fx` without `dur`. A take's clone length is already `audio_s`.

### Job queue

One worker runs jobs in order (the GPU does one generation at a time). The synchronous routes (`POST .../clone/generate`, `.../design/generate`) are unchanged and still block; the job routes are the async variants. Jobs are kept in memory and mirrored to `data/studio/_jobs.json` (last 100). Jobs still queued or running at a server restart come back as `failed` with the error `the studio server restarted before this job finished`.

**Submit**

- `POST /api/jobs` body `{kind: "clone"|"design", slug, items: [<body>...], fx?: [preset names], label?: string}`; 1 to 200 items.
- Shortcuts with `kind` and `slug` filled in: `POST /api/speakers/{slug}/clone/jobs` and `POST /api/speakers/{slug}/design/jobs`, body `{items, fx?, label?}`.
- Item bodies are the existing route bodies. Clone: `{text, guid?, reference: {wav, text?}, options: {cfg, timesteps, seed, use_instruct, retry_badcase, normalize, continuation}, instruct?}`; missing option keys take the defaults (`cfg 2.0, timesteps 10`, rest false). Design: `{description?, seed?, cfg?, timesteps?}`. `fx` is clone only and is applied to each finished take (a failed FX leaves the raw take and sets `item.fx_error`).
- **Seeds:** a blank seed is drawn by the server at submit time (`0 <= seed < 2^31`), so the response already carries every item's `seed`. A typed seed is kept. "One seed for all": send the same seed in every item.
- Returns the job (200). 400 for a bad kind, empty or oversized `items`, bad options, a reference outside `data/`, `fx` on a design job; 404 for an unknown speaker or a design job on a real speaker.

**Job record** (all job routes return this shape):

```
{ id: "j1760...", kind, slug, label,         // label defaults to "Generating" (clone) / "Designing" (design)
  state: "queued"|"running"|"done"|"failed"|"cancelled",
  total, done,                               // done = items finished OK
  index,                                     // 1-based number of the item running now / last started; 0 before start. "Take 3 of 6"
  items: [ { n, state: "queued"|"running"|"done"|"failed"|"cancelled",
             seed, cfg, timesteps, text,     // text = the clone line; null for design
             started_at, elapsed_s,          // elapsed_s live while running, fixed when finished
             take,                           // clone: take id (also in takes.json); null otherwise
             result,                         // clone: the full take (with fx once applied). design: {file, seed, cfg, timesteps, seconds, audio_s, description, text}, pass `file` to design/keep
             error, fx_error } ],
  takes: [take ids, in order],
  fx: [preset names], error,                 // job-level error (model down, restart)
  cancel_requested, created_at, started_at, finished_at,
  elapsed_s,                                 // since the job started; stops at finished_at
  expected_s,                                // mean `seconds` of this job's finished items, else of the speaker's last 20 takes; null if none
  current: { n, text, seed, cfg, timesteps, started_at, elapsed_s, expected_s } | null }   // the running item
```

State rules: `done` when the items ran (some may have `failed`); `failed` when every item failed, or the model was down (503), in which case the rest are `cancelled`; `cancelled` after Cancel. Other item errors do not stop the job.

**Read and cancel**

- `GET /api/jobs?active=1&slug=&limit=` returns a list of job records. With `active=1` only queued/running jobs, oldest first (the running one first). Without it, newest first (default limit 50). Poll this every 1 s while any job is active.
- `GET /api/jobs/{id}` returns one job (404 unknown).
- `POST /api/jobs/{id}/cancel` returns the job. A queued job becomes `cancelled` at once. A running job gets `cancel_requested: true`, its remaining items go `cancelled`, and the take in flight **cannot be aborted** on the GPU: when it lands its result is dropped (no take is saved, the item ends `cancelled`) and the job becomes `cancelled`. 409 if the job is already finished.

**Model health**

`GET /api/model/health` is now `{state}` as before, plus `job` while any job is queued or running:

```
{ state: "busy", job: { id, label, kind, slug, state, index, total, done, elapsed_s, expected_s, active_jobs } }
```

`state` reads `busy` while a job is active even if the backend says `ready` (it is between two takes); `down` stays `down`. `job` is the running job, else the first queued; `active_jobs` is the number of queued plus running. With no job the body is exactly `{state}`, as before.
