# Voice Studio, FX section: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (native) or subagent-driven-development. Steps use checkbox syntax.

**Goal:** An FX section in the studio: the preset library, the label-to-preset map for the harness effect labels, the expansion of both into `data/fx_lab/assignments.json` (the file `tools/fx_lab/batch.py` already reads), and the FX Lab page embedded with a clip-in / preset-saved bridge.

**Architecture:** The FX Lab (`tools/fx_lab/server.py`, :8908) stays a separate page and server; `batch.py` stays untouched. The studio reads `data/fx_lab/presets.json` and `tools/fx_lab/scenarios.json` for the library, owns `data/studio/fx_labels.json` (label -> ordered presets), and writes `assignments.json` only on an explicit request. The bridge is `postMessage` between the studio page and the FX Lab iframe, with the audio bytes sent in the message because the two origins cannot read each other's files.

**Tech Stack:** as slice 1.

**Spec:** parent spec section 3.3 and T4 (`docs/superpowers/specs/2026-10-09-voice-studio-design.md`). Where the spec is thin the numbered decisions below settle it.

## Global Constraints

Same as the Pools plan: local only, nothing deletes files, no commits or pushes unless asked (a "Checkpoint" step runs `git status`), dark UI only, no magic numbers, files under 500 lines. Server tests `cd tools/studio/server && python3 -m pytest tests -q`; web tests `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`.

## Decisions

1. **The library** is the names from `scenarios.json` plus saved presets from `data/fx_lab/presets.json` (the page's saved presets win on a name clash, as in `batch.py`).
2. **Labels** are the six the harness emits: `machine`, `vox_channel`, `helmet`, `ethereal`, `monstrous`, `cavernous`. A label maps to an ordered list of presets (series, in order). Unmapped labels expand to nothing. Saving a map that names a preset not in the library is a 400.
3. **Expansion to `assignments.json`:** `lines[guid]` for every unnamed line whose roster line carries `fx` labels, using the label map (labels in the order the harness gave them, presets de-duplicated, first occurrence kept); `speakers[name]` from each speaker's *active* studio profile (`data/studio/<slug>/active.json`, written by "Set active") when its `fx` list is non-empty. Per-line beats per-speaker in `batch.py`, so a line the harness labelled keeps its labels even if its speaker has a profile FX.
4. **Writing is explicit.** `GET .../assignments/preview` returns counts and a sample; `POST .../assignments` writes. If `assignments.json` exists it is first copied to `assignments.json.bak` (never deleted, overwritten on the next write).
5. **Bridge protocol.** Studio to FX Lab: `{type: "studio:load-clip", name, bytes: ArrayBuffer}`. FX Lab to studio: `{type: "studio:preset-saved", name}`. Each side checks `event.origin` against `http://127.0.0.1:<port>` / `http://localhost:<port>` for the other side's port and ignores anything else. This is one added listener in `tools/fx_lab/index.html` and one `postMessage` after a preset save.
6. **Entry point on a take:** each Results row gets "open in FX Lab", which navigates to `/fx?clip=<take raw path>`; the FX view fetches `/file?p=<path>` as bytes and posts it once the iframe has loaded.

## File structure

```
tools/studio/server/studio_server/fx_library.py     library, labels, expansion, preview, write            (Task 1)
tools/studio/server/studio_server/routes.py         + /api/fx/* routes                                    (Task 2)
tools/studio/server/tests/test_fx_library.py, test_fx_http.py
tools/fx_lab/index.html                             + message listener and preset-saved post             (Task 3)
tools/studio/web/src/composables/useFxBridge.ts     iframe bridge                                         (Task 4)
tools/studio/web/src/stores/fx.ts, api/types.ts, api/client.ts
tools/studio/web/src/components/fx/FxLibrary.vue, LabelMap.vue, AssignmentsPanel.vue
tools/studio/web/src/views/FxView.vue, router.ts, AppShell.vue (nav), results/TakeRow.vue (button)
```

## Tasks

### Task 1: `fx_library.py`

- `LABELS = ("machine","vox_channel","helmet","ethereal","monstrous","cavernous")`, `labels_path(cfg)`.
- `library(cfg) -> list[{name, source: "scenario"|"saved", dsp, notes}]` sorted by name, saved winning.
- `get_labels(cfg) -> {label: [preset]}` (every label present, empty list when unset), `save_labels(cfg, body) -> same` (400 on unknown label or unknown preset; atomic write under `STATE_LOCK`).
- `expand(cfg) -> {"speakers": {...}, "lines": {...}}` per decision 3, using `pools._roster`, `pools._unnamed_jobs` and `speakers.list_speakers` to find active profiles.
- `preview(cfg) -> {lines, speakers, sample: [...], unmapped_labels: {label: n}}`; `write(cfg) -> {path, lines, speakers}` per decision 4.
- Tests (`tests/test_fx_library.py`, on the pool fixture; extend `make_pool_repo` roster lines with `fx` labels and write `fx_lab/presets.json`): library merge and clash; labels default, save, 400 on unknown preset and unknown label; expansion order and de-dup; unmapped label reported and skipped; per-line labels kept when a speaker profile also has FX; speaker profile FX read from `active.json` only; preview does not write; write creates the file, then a second write leaves `assignments.json.bak`; a missing roster is a 404.

### Task 2: routes

`GET /api/fx/library`, `GET|POST /api/fx/labels`, `GET /api/fx/assignments/preview`, `POST /api/fx/assignments`. HTTP test `tests/test_fx_http.py` walks save labels, preview, write, bad preset 400.

### Task 3: FX Lab page listener

In `tools/fx_lab/index.html`: after `loadClip`, add `loadClipBytes(ab, name)` (decode and `rebuildBuffer`), a `message` listener accepting `studio:load-clip` from the allowed origins, and in the preset-save handler `window.parent !== window && window.parent.postMessage({type:"studio:preset-saved", name}, "*")` replaced by an origin-pinned target (the allowed studio origins are tried in order, stored on first message received; before any message, post to both). Verified in the browser (Task 5), not by a unit test: the page has no test harness.

### Task 4: web

Types and client for the new endpoints; `stores/fx.ts` (library, labels, preview; save and write actions); `useFxBridge(iframeRef, port)` (a pure `isAllowedOrigin(origin, port)` function exported and unit-tested; `sendClip(name, bytes)`; `onPresetSaved(cb)` registered on mount and removed on unmount); `FxLibrary`, `LabelMap` (six rows, ordered multi-select with up/down, Save), `AssignmentsPanel` (Preview counts, Write button, shows path); `FxView` (thin: sections plus the iframe `http://127.0.0.1:8908/`, reads `?clip=`, fetches `/file?p=` bytes after the iframe's `load`, posts them; on `preset-saved` reloads the library and shows the name); nav link; `TakeRow` "open in FX Lab" button (router push to `/fx?clip=`). Vitest: `isAllowedOrigin`, store actions, `LabelMap` emits ordered lists and blocks saving unknown presets via the server error, `AssignmentsPanel` preview then write, `FxView` posts the clip after load and reloads on `preset-saved`, `TakeRow` button navigates.

### Task 5: verification and docs

Full suites; real-data pass (library shows scenarios and saved presets; save a label map; preview counts against the roster's fx labels; do not write `assignments.json` on the real data without the owner's go: write once on a throwaway copy in tests only); browser pass with the real FX Lab server (:8908): open a take in FX Lab (clip loads, plays), save a preset there, see the studio react. README and CLAUDE.md lines.

## Self-review

Spec coverage: 3.3 two levels and bridge (Tasks 3, 4), label map and expansion (Tasks 1, 2), `assignments.json` format as `batch.py` reads it (Task 1). Gap by design: the FX Lab itself is not ported to Vue, only embedded (the spec says "embedded Faust page first"). Types: `assignments.json` shape `{speakers, lines}` matches `batch.py`'s docstring.
