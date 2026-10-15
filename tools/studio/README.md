# Voice Studio

A local Vue app and small Python API for working on one speaker's voice at a time: pick or design a source clip,
clone it onto test lines, apply FX, rate the takes. Design notes are in
`docs/superpowers/specs/2026-10-09-voice-studio-design.md`. This first slice covers the Speakers section and replaces
the voice audit page (:8907) and the Pasqal lab (:8910).

## Run

    ./tools/studio/run.sh

Then open http://127.0.0.1:8930. The script builds the web app on first run. Set `STUDIO_PORT` to change the port.

The model is a separate process. Start it only when the GPU is free:

    /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/voice_design/live_backend.py

### Model on another machine (the Windows 4070)

The backend can run on another machine and be reached through an ssh tunnel, so nothing is exposed on the LAN:

    # on the Windows box (detached; uses its own VoxCPM2 env and a copy of tools/voice_design/{design,live_backend}.py)
    ssh win-gpu 'cmd.exe /c cd /d C:\Users\geoff\rt-tts\repo && C:\Users\geoff\rt-tts\.venv-vox\Scripts\python.exe -u tools\voice_design\live_backend.py --host 127.0.0.1 --port 8909'
    # here
    ssh -N -L 127.0.0.1:8909:127.0.0.1:8909 win-gpu &
    python3 -m studio_server --port 8930 --remote-backend

`--remote-backend` makes the studio send each reference clip with the request and save the returned audio under
`data/voice_design/live_tmp`, since the two machines share no files. A backend whose host is not localhost does this
automatically. Windows Firewall blocks inbound connections to the Anaconda Python there, which is why the tunnel is used.

Without a model the studio still works for listening, ranking, verdicts and profiles. Live design and clone generation are
disabled and say why.

## Develop

    cd tools/studio/web && npm run dev        # Vite on :5173, proxies /api and /file to :8930
    cd tools/studio/server && python3 -m pytest tests -q
    cd tools/studio/web && npm test && npm run typecheck

`server/tests/run_mock_stack.py <dir>` serves the app on a throwaway fake repo with a mock model, for browser checks
that need no GPU and no real data.

## Browser suite (`npm run e2e`)

    cd tools/studio/web && npm run e2e                       # whole suite, about 40 s
    npx playwright test e2e/pedalboard-save.spec.ts          # one spec
    npx playwright test -g "stomp"                           # one test by title

It builds the web app into `web/node_modules/.e2e-dist` when a source file is newer (the real `dist` and the running Studio are not touched),
starts `server/tests/run_mock_stack.py --pedalboard` on a free port with a fresh directory under the system temp folder, runs Playwright
Test against it and stops the server. It never reads or writes the real `data/`: the block library and the starters are copied into the
fake root, so a Save in a test lands only there (the vendored FaustWasm under `tools/fx_lab/vendor` is served from the repo, read-only).
Needs the system `python3` (numpy for the game-voice reference) and a Chromium: it uses the one the Playwright MCP downloaded under
`~/.cache/ms-playwright`, otherwise run `npx playwright install chromium`.

Covered: the pedalboard loads with no console errors or failed requests, the palette (31 pedals, 7 categories), a starter's 14 nodes,
13 drawn wires, no overlap, inside the canvas, readable zoom, compile once, playback with a stereo reading and a spectrum, knobs do not
recompile, adding and wiring recompiles once (also for a burst of changes), a taken input refuses a wire, the stomp switch, save and
reload round trip on disk, the nav link, and the Casting, BG3 Voices, RT Voices and Assignments pages loading without errors.
Tests read page state through `window.__pedalboard` (`src/qa/pedalboardQaHook.ts`), which exists only in dev or with `?qa` in the URL.

Traces and failure screenshots go to `web/test-results/` and `web/playwright-report/` (both git-ignored; open a trace with
`npx playwright show-trace <trace.zip>`). Each run leaves its temp directory behind under the system temp folder, named `rt-studio-e2e-*`.

## Where state lives

- `data/studio/<slug>/profile.json`, `takes.json`, `active.json`, `fx/`
- Existing files, reused as they are: `data/voice_design/{audit,design_manifest,overrides,scores}.json`,
  `data/voices/{catalog.json,prompts/prompts.json}`, `data/render/*`, FX Lab presets.

Rankings and verdicts write to the real `audit.json`. "Register pick" writes to the prompt bank.

## Pools

`/pools` routes every unnamed priority-3 line (`default_speaker`) to a voice: a known speaker's real bank, a named NPC
without a bank, the narrator, or a shared **slot** (`pool_<id>`, registered as a designed speaker so the Speakers page
designs, ranks and registers its voice). Routes and slots live in `data/studio/pools.json`. Rebuild re-derives the
automatic routes and keeps your overrides, renamed slots and spot-check marks. The review queue is grouped by roster
entry; `match_decisions.json` (written by the match review page) overrides the matcher. `tools/render_corpus/plan.py`
reads `pools.json`; re-running `plan.py` is what makes the routes take effect in `jobs.jsonl`, and that run is the
owner's call (it rewrites the job list).

## FX

`/fx` embeds the FX Lab (port 8908, `python3 tools/fx_lab/server.py`), lists the preset library (scenarios plus saved
presets), edits the label map (`data/studio/fx_labels.json`: harness label to ordered presets) and expands it, plus the
active speaker profiles, into `data/fx_lab/assignments.json` for `tools/fx_lab/batch.py`. Preview first; Write keeps the
previous file as `assignments.json.bak`. "open in FX Lab" on a take sends its audio into the FX Lab page, and saving a
preset there shows up in the studio. The bridge is `postMessage` pinned to the two local origins; it needed one listener
added to `tools/fx_lab/index.html`.

## Matches

`/matches` replaces `tools/npc_profile/match_review.py`: confirm or overrule each proposed roster-entry-to-known-speaker
match. Decisions save to the same `data/npc_profile/match_decisions.json`, and a save rebuilds the Pools routes when they
exist. Use this page or the old one, not both at once (last write wins).

## Render QA

`/qa` replaces `tools/render_corpus/audit_server.py`: listen to rendered clips from the merged export
(`data/render/export/index.json`, about 11,000 clips) or one render run, filter by speaker, reference, engine, flag and
verdict, and mark each good or bad with tags and a note. Clips are compared against their clone reference, the earlier
render and the game's own line. Verdicts go to the same `data/render/audit/verdicts[_<run>].json` files. The compressor
A/B (`x`) needs numpy and scipy. Keys: j/k move, space plays, g good, b bad, u clear, n next unjudged. Use this page or
the old one, not both at once.

## Carried over from the old pages

The old audit page's conveniences live in Speakers: previous/next speaker with an "N / total, M picked" count, a picked
marker in the list, clone-test renders and score chips on each candidate, live design takes kept per speaker for the
session, new takes autoplaying, and "Register all picks" (asks first, lists any it had to skip). Render QA shows a
per-reference good/bad tally and the game's own line as "Real: <speaker>". Pools can merge two slots (a merge is a
rename, so Matches decisions still apply afterwards). Not carried over: the old page's in-browser FX sliders (the FX Lab
replaces them) and the `--only guids.txt` run subset.

## Still around

Nothing is left to replace. `tools/_old_pages/` holds the retired pages until they are approved for trashing.

## Verified on the model

On the Windows 4070 through the tunnel (2026-10-09): live design (about 2.4 s), clone from a real clip (about 2.1 s), and
seed reproducibility: the same seed twice gave byte-identical wav files, a different seed did not. Not repeated on
another GPU.

Also done through the browser against the real model (throwaway fake data, `run_mock_stack.py --backend ...`): a clone
batch of 2 sources x 2 lines with FX (4 takes in about 17 s), live design, Keep (the new candidate has a recorded seed),
arrow and drag ranking, stars, accent, Register pick, clear FX.

## Not yet verified

Nothing known. Real-data runs of the studio have only used the model off or the test stacks above, so the first real
audition will be the first time rankings are written by hand.

## Casting

`/casting` gives each character that has no voice a real BG3 voice. Characters come from
`data/npc_profile/describe/casting_needs.json` (303, sorted by line count, so the biggest characters are cast first), BG3 voices from
`data/bg3_voices/catalog.json` (about 440 with reference clips), portraits from `data/portraits/half/` (extracted from the game's
`portraits` bundle with UnityPy; matched by name, with a picker to correct a wrong or missing one). Suggestions pair big with big:
a character near the top of the list is offered BG3 voices near the top by line count, filtered by gender and by creature or human.
"Audition" clones the BG3 reference onto one of the character's real lines through the model backend (start it and the tunnel as
above, so it needs the GPU); without the backend you can still listen to the BG3 reference clips and cast.

State: `data/studio/casting.json` (assignments, portrait corrections). "Register cast voices" copies each chosen BG3 reference to
`data/voices/prompts/cast/` and replaces that character's entry in `prompts.json` (the previous file is kept as
`prompts.json.pre-casting-<time>`). `tools/render_corpus/plan_voiceless.py` uses a speaker's own registered voice first, so the next
render picks the cast voice up. `data/bg3_voices/` and `data/portraits/` are game assets: local only, git-ignored.

### BG3 voice labels and the nameless groups

`/voices` is where each BG3 voice gets labels, once: gender (male, female, neuter), age (child, youth, adult, old), class (low, middle, high),
processing (natural, processed) and pitch (high, middle, low) count toward "fully labelled"; optional extras are accent, what it sounds like
(human, elf, dwarf, orc, devil, undead, construct...), texture, manner, pace, a 1 to 5 rating, a use flag (free, reserve for main characters,
do not use) and a note. A dashed chip is an automatic guess (gender from the catalog, pitch from the median F0): click it to confirm. The
label set is data (`SCHEMA` in `server/studio_server/bg3_labels.py`), so adding a label is one entry. Labels live in
`data/studio/bg3_labels.json` (a backup copy is kept at least every half hour while you label).

The Casting page filters the BG3 voices by those labels (chips under the tabs; "Match this character" fills in gender and age from the
character). Nameless speakers are casting targets too: each pool slot from the Pools page appears under "Nameless groups", so you can cast a
BG3 voice for, say, every nameless low-class young woman by creating that slot in Pools. Casting a slot replaces that slot's voice in the
prompt bank, and `tools/render_corpus/cast_ready.py` re-renders every cue routed to it.

## Render Lab (`/lab`)

An interactive lab for tuning how one cast speaker's lines are rendered (built 2026-10-13 for the Vladaym pilot). Pick a line, change the
recipe (cfg, steps, seed, style prefix, pronunciation overrides, what each punctuation mark becomes, how the text is split and the silence
between pieces), render on the live model, and compare against the current render. A take keeps its recipe, rating and notes in
`data/studio/lab/<speaker>/` (takes are hidden, never deleted). Server: `lab.py` (batches on a thread), `lab_text.py` (the text stages),
`lab_audio.py` (silence, peak limit, metrics); web: `views/LabView.vue`, `components/lab/`, `stores/lab.ts`.

- The model is the shared `tools/voice_design/live_backend.py` (port 8909, one generation at a time). It now writes float wavs, so a peak
  past full scale is measured (`model_peak`) instead of silently clipped, and it passes `retry_badcase_*`, `max_len` and `min_len` through.
- Metrics per take: crest factor of the speech frames (peak over rms, dB; under 11 dB sounds compressed/overdriven), clipped runs, model peak.
- Pronunciation overrides live in the recipe (word, arpabet|plain|literal, value); the shared lexicon is looked up, never edited.
  `GET /api/lab/real-clips?q=word` lists the game's own clips containing a word, for matching how it is really said.
- A recipe is meant to become per-job fields the render worker honours (`cfg`, `timesteps`, pre-split pieces, `respell: false`): that bridge
  is not built yet. `render.py` still uses `CFG = 3.0` and the planners their 1,200-char cap.
- `tools/render_corpus/clip_scan.py` scans raw renders for clipped runs.

### Recipe renders (the lab's recipe on the render workers)

`plan_recipe.py --speaker NAME --recipe RECIPE` writes one job per speech piece with the recipe attached; run it as its own queue
(`queue_server.py --run cast-r2 --jobs ... --port 8953`) and start workers against it (the worker honours `job["recipe"]`, keeps float wavs and runs
the quality ladder). `recipe_followup.py` queues `@fix` takes for what is still flagged; stitch with `--runs cast-r2 cast` into a new directory
(the stitcher skips cues already in its manifest) and overlay it last in `night_build.py`. Job schema: `docs/superpowers/specs/2026-10-13-recipe-render-jobs.md`.
The workers on other machines need `render.py`, `worker.py`, `recipe_*.py` copied over (scp) before they can take recipe jobs, and the lab's model
and a 5080 worker cannot be loaded together (10.7 GB each).
