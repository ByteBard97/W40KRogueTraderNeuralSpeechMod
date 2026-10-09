# Voice Studio first slice, part 7 of 7: Integration and verification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Task 15. Build, serve, browser verification, live-model check, docs.
**Previous part:** [Lines, options, FX and results](06-lines-options-fx-results.md). **Next part:** none.

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

---

### Task 15: Build, serve, browser verification, docs, spec update

**Files:**
- Create: `tools/studio/README.md`, `tools/studio/run.sh`, `tools/studio/server/tests/run_mock_stack.py`
- Modify: `docs/superpowers/specs/2026-10-09-voice-studio-design.md` (apply the three deviations)

- [ ] **Step 1: Production build**

Run: `cd tools/studio/web && npm run build`
Expected: type check and Vite build succeed; `tools/studio/web/dist/index.html` exists.

- [ ] **Step 2: Write `run.sh` and the README**

`tools/studio/run.sh`:

```bash
#!/usr/bin/env bash
# Build the web app if needed, then start the Voice Studio API server on :8930.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f web/dist/index.html ]; then
  (cd web && npm install && npm run build)
fi
cd server
exec python3 -m studio_server --port "${STUDIO_PORT:-8930}" "$@"
```

`tools/studio/README.md` covers: what it is (one paragraph pointing to the spec), how to run (`./tools/studio/run.sh`, then open http://127.0.0.1:8930), how to start the model (`/home/geoff/anaconda3/envs/roguetts/bin/python3 tools/voice_design/live_backend.py`, only when the GPU is free), dev mode (`cd web && npm run dev`, with the API server on 8930), tests (`cd server && python3 -m pytest tests -q`, `cd web && npm test`), where state lives (`data/studio/<slug>/{profile,takes,active}.json`, plus the existing voice_design files), and which old pages this replaces (:8907 audit, :8910 Pasqal lab) and which stay (FX Lab :8908, matches :8920, render QA :8951). Plain wording; no marketing language.

Then `chmod +x tools/studio/run.sh`.

- [ ] **Step 3: Full automated pass**

Run:
```bash
cd tools/studio/server && python3 -m pytest tests -q
cd ../web && npm test && npm run typecheck
```
Expected: everything green.

- [ ] **Step 4: Browser verification against the real data, model off**

Start `tools/studio/run.sh` (background; note the PID from `ss -ltnp | grep :8930`). Back up the real state first:

```bash
S=/tmp/claude-1000/-home-geoff-projects-games-W40KRogueTraderNeuralSpeechMod/cfeb1f31-c9bd-483d-bff2-26fc2e9d570a/scratchpad
cp data/voice_design/audit.json data/voice_design/design_manifest.json data/voice_design/overrides.json $S/ 2>/dev/null; ls $S
```

Using the Playwright MCP tools, check each item and record pass or fail:

1. `/speakers` lists 35 speakers in **two** groups (23 real speakers under "Has a source", 12 designed under "Needs a voice"; the "Profile saved" group is empty and hidden until item 5 saves a profile); Pasqal and a designed NPC are present; the filter box works; the model status says `down`.
2. Open Pasqal: 45 clips listed, 12 labelled curated, play works; 844 lines, only 200 rendered with a "Show 200 more" button; baseline play buttons work; emotion chips filter; "Pick 6 spread" selects up to 6.
3. Generate is disabled and the reason text is shown while the model is down.
4. Open a designed NPC (Vox Master Vigdis): candidates listed with p_us chips; keyboard buttons move a candidate and the order persists after reload. **Undo any ranking you create** (post an empty order) so the real audit data is as before; compare with the backup copy.
5. Save a profile for Pasqal with a ticked clip; `data/studio/pasqal/profile.json` appears; "Set active" writes `active.json`. These two new files are the only expected additions under `data/studio/`.
6. Unknown route `/speakers/nobody` shows an error message, not a blank page. A path like `/file?p=../README.md` returns 404.

- [ ] **Step 5: Browser verification of keep, generate, FX and register, against the mock backend (no GPU, no real data)**

Everything the real-data pass cannot do with the model off runs here against a throwaway fake repo and the mock model backend. First create `tools/studio/server/tests/run_mock_stack.py`:

```python
#!/usr/bin/env python3
"""Serve the studio against a throwaway fake repo and a mock model backend. No GPU, no real data.

  python3 tests/run_mock_stack.py <dir> [--port 8931]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest import make_repo  # noqa: E402
from mock_backend import MockBackend  # noqa: E402
from studio_server.app import make_server  # noqa: E402
from studio_server.model import ModelClient  # noqa: E402

REAL_REPO = Path(__file__).resolve().parents[4]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--port", type=int, default=8931)
    a = ap.parse_args()
    root = Path(a.dir)
    root.mkdir(parents=True, exist_ok=True)
    cfg = make_repo(root)
    real_venv, link = REAL_REPO / "tools/fx_lab/.venv-fx", root / "tools/fx_lab/.venv-fx"
    if real_venv.is_dir() and not link.exists():
        link.symlink_to(real_venv)          # lets "apply FX" run for real (CPU only) on the fake data
    mock = MockBackend(cfg.voice_design)
    print(f"Voice Studio (mock model, fake data in {root}) on http://127.0.0.1:{a.port}", flush=True)
    make_server(cfg, ModelClient(mock.url), a.port).serve_forever()


if __name__ == "__main__":
    main()
```

Start it in the background with the scratchpad as the data dir (`python3 tools/studio/server/tests/run_mock_stack.py $S/mockstack --port 8931`; stop it later by PID from `ss -ltnp | grep :8931`). With the Playwright MCP tools on http://127.0.0.1:8931 check, recording pass or fail:

1. The model status turns `ready` and Generate buttons are enabled.
2. **Design:** open Muaran; Generate with seed 4242; a take appears with `seed 4242` and plays; Keep it; a new candidate `c2` shows with a recorded seed (no "no recorded seed" marker) and `gen.description`/`text` are present in the fake `design_manifest.json`; drag or arrow-move it to rank 1; Register pick succeeds and `prompts/designed/muaran.wav` exists in the fake data dir.
3. **Clone:** open Pasqal; tick the clip and "Pick 6 spread" (the fake data has 2 lines, so tick both); Generate 2 takes; each Results row offers source clip, bank, raw clone buttons and all play; both lines used one seed each.
4. **FX:** choose the `Clean` preset and apply it to a take: an `fx` button appears and plays. Clear the picker and click "re-apply FX": the fx clip must remain (the take keeps its presets).
5. Rate a take with stars and reload: the rating persists. Save a profile and "Set active": `data/studio/pasqal/profile.json` and `active.json` exist in the fake data dir.
6. Stop the mock backend process and click Generate again: the page shows the 503 message and the earlier takes remain.

- [ ] **Step 6: Live check with the model (only when the user says the GPU is free)**

Start `live_backend.py`, reload the page, and confirm: status turns `ready`; Generate in the live-design box returns a take in a few seconds; Keep adds a candidate; a clone batch of 2 lines x 2 sources makes 4 takes sharing a seed per line; apply FX makes a processed clip; and the **reproducibility check**: generate with seed 4242 twice and compare the two raw WAV files byte-for-byte (`cmp`); record the result in `tools/studio/README.md` (equal or not). If this step is not possible now, leave it listed under "Not yet verified" in the README.

- [ ] **Step 7: Reconcile the spec with what was built**

The spec already records the decisions above. Check section 5.1's route table against Task 6's table and fix any differences (the spec lists `/api/design/...` and `/api/clone/...`; the built routes are under `/api/speakers/{slug}/...`), and note that "loading" is shown as `down`. T6's active file is `data/studio/<slug>/active.json`.

- [ ] **Step 8: Final checkpoint, independent review**

Run `git status --short` and list for the owner what is new. Ask whether to commit. Stop the dev and mock servers by PID. Then ask for a fresh independent reviewer (a subagent on the most capable model, or the advisor) to read the whole `tools/studio/` tree against the spec: the defects found so far were integration-level ones, the kind the author of both sides misses.
