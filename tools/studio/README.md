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
