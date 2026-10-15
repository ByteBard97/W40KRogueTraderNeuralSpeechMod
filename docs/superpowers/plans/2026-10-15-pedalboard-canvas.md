# Pedalboard canvas: plan

Goal: a browser page (Voice Studio, `/pedalboard`) where the owner drops effect pedals on a canvas, wires them freely, flips pedals on and off and turns knobs live, hears the result in headphones in stereo, and saves the setup as a preset that `batch.py` applies to a raw voice reproducibly. Rewiring may recompile; sound already playing is not disturbed.

## Decisions (settled with the advisor, 2026-10-15)

1. **One generated Faust program per graph**, not a Web Audio graph of nodes. The editor saves the generated `.dsp` text next to the graph; the batch side compiles that saved text and never needs the generator.
2. **Every wire is stereo.** Each block is 2-in 2-out at graph level. Mono effects are doubled with `par(i, 2, fx)` inside the node (one set of knobs drives both sides). Stereo-native blocks (auto pan, stereo chorus, stereo phaser, bass spread) stay as they are. The Input node duplicates the mono clip to L and R.
3. **Each node instance is wrapped in `vgroup("<nodeId>", ...)`** so two copies of one block get separate controls. A control's key everywhere (browser engine, DawDreamer, presets) is `${nodeId}_${short(label)}`, where `short` replaces runs of non-alphanumerics with `_` and trims `_`. **Every consumer derives it from the control's full address with the root segment stripped** (`/fx/n1/Ring_Hz` becomes `n1/Ring_Hz` becomes `n1_Ring_Hz`; DawDreamer's `name` is `/dawdreamer/n1/Ring_Hz`) and **never reads FaustWasm's `shortname` field**: Faust shortens it to the shortest unique suffix, so with one Ring Mod it is `Ring_Hz` and adding a second changes it to `n1_Ring_Hz`, which would break parameter carry-over on every node addition. **The generated program must be `process = vgroup("fx", <graph>)`**: when a program's top level is a single group, Faust makes that group the root and drops it from the address (`/n1/Gain`), so there is no root segment to strip and the key would come out as `Gain`. With the outer `fx` group the address is always `/fx/<nodeId>/<label>` (verified in both runtimes). Note DawDreamer's `label` is only the last segment (`Gain`), so keying by label collides for two instances.
4. **Fan-in is an explicit Mix node** with a level knob per input; no automatic 1/N scaling. Fan-out is just several wires from one output. No feedback loops in v1 (cycles are refused when a wire is made).
5. **Generator**: topological layers of the DAG; between layers a Faust `route(...)` picks and duplicates wires, with `_` pass-throughs for wires skipping a layer; `route` indices are 1-based. The whole block library text is inlined into every program, so FaustWasm and DawDreamer see identical source.
6. **Live vs recompile.** Knob and stomp changes call `setParamValue` live. Any wiring or node-set change regenerates, compiles a new node in the background, then crossfades to it over ~50 ms, carrying parameters over by key.

## Contracts (the workers build against these; do not change without telling the lead)

### Catalog (`tools/fx_lab/faust/catalog.json`, generated from `blocks.lib` by `tools/fx_lab/build_catalog.mjs`)
```json
{"version": 1, "blocks": [{
  "id": "metal", "name": "Metal bank", "category": "Metal", "description": "one sentence",
  "kind": "effect",                       // "effect" | "structural"
  "stomp": "Metal on",                    // label of the on/off checkbox (null for structural blocks)
  "inputs": 1, "outputs": 1,              // number of STEREO wires in and out (input node: 0/1, output node: 1/0, mix2: 2/1)
  "node": "node_metal",                   // Faust identifier: a box with 2*inputs inputs and 2*outputs outputs
  "stereoNative": false,
  "controls": [{"label": "Metal base Hz", "type": "hslider", "init": 300, "min": 80, "max": 1200, "step": 1},
               {"label": "Metal on", "type": "checkbox", "init": 1, "min": 0, "max": 1, "step": 1}]
}]}
```
Categories (tab names in the UI): `Tone`, `Pitch & voice`, `Metal`, `Modulation`, `Space`, `Stereo`, `Routing`, `Output`.

### Graph (`graph.json`, schema version 1)
```json
{"version": 1, "name": "pasqal-test",
 "nodes": [{"id": "n1", "type": "input", "x": 0, "y": 0},
           {"id": "n2", "type": "freqshift", "x": 220, "y": 0, "on": true, "params": {"Freq shift Hz (negative shifts down)": 35}},
           {"id": "n3", "type": "output", "x": 440, "y": 0, "params": {}}],
 "edges": [{"id": "e1", "source": "n1", "target": "n2", "targetPort": 0},
           {"id": "e2", "source": "n2", "target": "n3", "targetPort": 0}]}
```
`params` is keyed by control **label**; missing = the control's init. `on` defaults to true. Node ids match `^[A-Za-z][A-Za-z0-9]*$`. Exactly one `input` and one `output` node. A single-input port accepts at most one wire. A node may feed many wires.

### Generator (TypeScript, `tools/studio/web/src/pedalboard/`)
```ts
generate(graph, catalog, libText): { code: string; controls: Control[] }   // throws GraphError
validate(graph, catalog): GraphIssue[]       // {code, message, nodeId?, edgeId?}; codes: unknown-type, cycle, port-taken, bad-port, missing-input, no-path, duplicate-id, bad-id
paramsFor(graph, catalog): Record<string, number>   // flat key -> value, stomp as 1/0, defaults filled in
controlKey(nodeId, label): string
// Control = {key, nodeId, label, type, init, min, max, step}
```
`process` of the generated program is `vgroup("fx", <graph>)`: one mono input, two outputs. A CLI `npx vite-node src/pedalboard/cli.ts -- <graph.json> [--catalog path] [--lib path]` prints `{code, controls, params}` JSON, so Python tests can use the generator.

### Presets
A preset entry in `data/fx_lab/presets.json` stays `{dsp, params, notes}` (existing format) and gains `graph`:
`{"dsp": "presets/<name>.dsp", "params": {<key>: value}, "graph": {...}, "notes": ""}`. `dsp` is a path under `tools/fx_lab/faust/`; the saved `.dsp` is the generated program. Batch uses `dsp` and `params` only.

### Studio server (Python, `studio_server/pedalboard.py`)
`GET /api/pedalboard/blocks` -> `{lib: "<blocks.lib text>", catalog: {...}}`; `GET /api/pedalboard/graphs` -> `[{name, updated}]`; `GET /api/pedalboard/graphs/{name}` -> graph; `POST /api/pedalboard/graphs` `{graph, code, params, notes}` saves `data/fx_lab/graphs/<name>.json`, writes `tools/fx_lab/faust/presets/<name>.dsp` and the preset entry; names `^[A-Za-z0-9_-]{1,60}$`; writes are atomic.

## Work packages and tests

Each worker owns only the files listed, runs its tests, and does not commit (the lead commits). Shared rules for every worker: never delete files (ask the lead; `gio trash` only on approval), no `git push`, no AI attribution anywhere, dark theme only, no secrets, files under 500 lines, match surrounding style, UI copy has no em dashes.

**Phase 0 (lead, inline):** W2 parameter addressing, with its tests and the advisor's extra test (a program with one vgroup'd instance and the same program with two both yield `n1_<label>` for n1 in both runtimes). Commit, then spawn Phase A.

**Phase A (independent, run in parallel; W1 is the long pole, start it first)**

- **W1 Faust block library.** Files: `tools/fx_lab/faust/blocks.lib`, `tools/fx_lab/build_catalog.mjs`, `tools/fx_lab/faust/catalog.json`, `tools/fx_lab/tests/test_blocks.py`. `chain_v1.dsp` (a copy of today's `chain.dsp`) is the oracle and stays unchanged. Convert every effect in `chain_v1.dsp` into a self-contained block (its controls and helpers inside a `with {}`), with its own `on` checkbox, as `node_<id>` (2 in, 2 out; mono effects via `par(i, 2, ...)`). Add `node_mix2/3/4` (level dB per input, default 0), `node_output` (Output dB, limiter threshold, hard clip, stereo) and `input` (structural). Tests: for each block, a one-block program (`process = _ <: (_,_) : vgroup("n1", node_x)`, both output channels) with chosen params compared to the same effect in `chain_v1.dsp` with the same settings, **compared from 0.25 s on** because each stomp fades in with `si.smoo` (correlation at least 0.9999, relative RMS at most 1e-3, both channels); bypass (on = 0) is transparent; two instances in different `vgroup`s have independent controls; a mono block's two channels are identical for identical input; `catalog.json` equals a fresh rebuild; every block compiles in both DawDreamer and FaustWasm.
- **W2 Parameter addressing (done by the lead before the others start).** Files: `tools/fx_lab/dd_render.py`, `tools/fx_lab/render_wasm.mjs`, `tools/fx_lab/null_test.py`, `tools/fx_lab/tests/test_addressing.py`. Key DawDreamer parameters by the Faust shortname form of the path (`short(name minus the "/dawdreamer/" prefix)`); keep every existing flat-chain test passing unchanged. Tests: a fixture program with two `vgroup`s holding the same label gives two distinct keys in both runtimes and setting one does not move the other; flat `chain_v1.dsp` keys are unchanged; unknown keys are ignored as today.
- **W3 Graph generator.** Files under `tools/studio/web/src/pedalboard/`: `types.ts`, `graph.ts` (validate, params), `generate.ts`, `cli.ts`, plus `__tests__/`. Pure TypeScript, no Vue. Ship a tiny fixture `blocks.lib` (`node_gain`, `node_mix2`, `node_output`) and a fixture catalog. Tests (vitest) against them, **including a compile test**: shell out to `tools/fx_lab/render_wasm.mjs` on the generated series graph and the split/merge graph, so golden text can never enshrine invalid Faust. Other tests: series; split and merge through a Mix; skip connection; fan-out; two instances of one block give distinct keys; stomp and params mapping; every validation code; cycle rejection at edge-add time via an exported `canConnect(graph, catalog, edge)`; golden snapshots of generated text for three graphs; the CLI round trip.
- **W4 Server endpoints.** Files: `tools/studio/server/studio_server/pedalboard.py`, route lines in `routes.py`, `tests/test_pedalboard.py`. Tests: blocks endpoint returns lib and catalog; graph save writes graph, `.dsp` and preset entry atomically; name validation and path traversal rejected; list and load round trip; saving twice overwrites.

**Phase B (after A)**

- **W5a Editor canvas.** Files under `tools/studio/web/src/` : `views/PedalboardView.vue`, `components/pedalboard/*`, `stores/pedalboard.ts`, route and nav entry, and `package.json` (add `@vue-flow/core`, `@vue-flow/background`, `@vue-flow/controls`). Palette (by category), pedal nodes (name, LED, stomp switch, slider rows, collapse), Input/Output/Mix nodes, wiring with `canConnect`, delete, save/load via the server, dark tokens. Tests (vitest, vue-test-utils): the store's add/remove/move/connect/disconnect/params/on operations, refusal of cycles and second wires into a taken port, node component renders controls from the catalog and emits param and stomp events, palette lists categories, save/load calls the API.
- **W5b Audio engine and monitor.** Files: `composables/useGraphEngine.ts`, `components/pedalboard/MonitorPanel.vue`, `utils/audioMonitor.ts`. Compile the generated code with FaustWasm, set params live by key, 50 ms crossfade swap with parameter carry-over, transport (clip loop, raw bypass), the average-spectrum-against-game-clip view and stereo scope ported from the FX Lab page. Tests (vitest, fake AudioContext and fake node): param carry-over by key on swap, crossfade ramps, stale compile discarded when a newer one finishes first, band-power maths against a synthetic spectrum.
- **W7 Batch.** Files: `tools/fx_lab/batch.py`, `tools/fx_lab/tests/test_batch.py` additions. Presets with a `dsp` under `presets/` render through the saved program with `params` by key; stereo output as now. Tests: a graph preset renders identically to a direct DawDreamer render of its saved `.dsp`; two-instance preset honours both instances' params; mono result stays mono when sides are identical.

**Phase C (after B)**

- **W6 Presets.** Files: `tools/fx_lab/migrate_scenarios.py` (scenarios.json to graph presets via the generator CLI), new Rogue Trader stereo starting points (tech-priest, servitor, machine spirit, vox-caster, helmet, ghost or psyker, daemon, Necron, and Pasqal-target stereo), tests: each migrated scenario's generated program matches the old scenario rendered through `chain_v1.dsp` (same tolerance as W1); each new preset compiles, peaks under 0.99 and has a finite spectrum.
- **Lead:** integration null test (generated chain of all blocks equals `chain_v1.dsp`), Playwright check of the page (drag, wire, stomp, knob, rewire, save, load, play), full test runs, commit.

## Known limits (shown in the UI or noted)

Parallel branches whose blocks add different delay (pitch shifter, Hilbert pair) comb-filter where they merge. The bank builder has not been verified to accept stereo clips (check `tools/bnk_patch` before promising stereo in game). First recompile of a large graph takes a second or two.
