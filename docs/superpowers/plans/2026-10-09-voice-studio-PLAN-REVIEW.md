# Review: Voice Studio first-slice implementation plan (2026-10-09)

Reviewer: Kimi. Scope: the overview (`2026-10-09-voice-studio-first-slice.md`), all seven sub-plans
(`2026-10-09-voice-studio/01`–`07`), and the updated spec. Method: three independent passes over the sub-plans
(server, web foundation/shell, source/lines/integration), with every load-bearing claim traced against the real
repo (`live_backend.py`, `audit_server.py`, `design.py`, `batch.py`, the data files) and contested findings
re-verified by the reviewer directly.

**Verdict: no blockers. The plan is unusually well-grounded — the backend contract, data schemas, route table,
and cross-task type interfaces all check out against reality. But the overview's self-review overclaims: its
"placeholder scan" is inaccurate, and its final verification gate (Task 15) contains checks that will fail
against real data. Six should-fixes, all small and textual. Fix them before execution, because this plan will
be read as an executable script.**

## 1. Should-fix findings

### 1.1 Task 15's browser checklist will fail against real data — the plan's own final gate is wrong
`07-integration.md:75` expects `/speakers` to show "35 speakers in three groups". But `SpeakersView` filters
out empty groups (`04-web-shell-and-speakers.md:473`), and at verification time there are zero saved profiles
(`data/studio/` is empty; item 5 of the same checklist creates the first profile *after* item 1 asserts the
groups). Real data yields exactly **two** groups: 23 real speakers (all `source`) + 12 designed (all
`needs_voice`, since Vigdis's `pick` is null). An executor running this checklist will hit a "failure" that is
the plan's error, not the app's.

### 1.2 Task 15 silently drops spec §8's e2e coverage of "keep, generate, apply FX"
Spec §8 requires browser checks against the built app **with the mock backend**, covering rank, keep, generate,
apply FX, save profile. Task 15 Step 4 runs against real data with the model **off**, so keep, generate and
apply-FX are never exercised in a browser at all — only rank, save-profile and disabled-generate. This is not
forced by the GPU constraint: the mock backend exists (Task 5) and the server CLI already has `--backend`
(`02-server-live-and-api.md:857-863`), so a second browser pass against the mock over a fake/copied data dir
covers all five operations with no GPU and no risk to real data. As written, three of the five spec'd e2e
behaviors rest only on unit tests plus a conditional manual GPU check.

### 1.3 TakeRow's "re-apply FX" button silently deletes the FX version
`06-lines-options-fx-results.md:546`: `canApply = ctx.fxChosen.value.length > 0 || !!props.take.fx`. If a take
has FX and the user has cleared the preset picker, the button is enabled and labelled "re-apply FX", but
`applyFx()` sends an empty preset list — and the server treats empty presets as *clear*
(`02-server-live-and-api.md:607-608`: `if not presets: return update_take(..., fx=None)`). One click labelled
"re-apply" removes the FX clip. Fix: when `fxChosen` is empty and `take.fx` exists, re-send `take.fx.presets`
(or disable with a hint).

### 1.4 Results rows omit the playable real/source clip the spec explicitly requires
Spec §3.1 item 5 and §6 both specify `ClipCompare` rows of **real clip / bank / raw clone / FX** — and the
whole T1 difficulty (Pasqal's doubly-processed sources) hinges on hearing the source next to the clone.
`TakeRow.vue` (`06:540-544`) builds only bank/raw/FX; the source appears as a text label. The reference path is
already on the take (`take.reference`), so this is a one-line fix plus a test update — but if executed as
written, the plan delivers a Results section that fails the spec's central comparison.

### 1.5 `design/keep` accepts missing `description`/`text`, producing non-reproducible candidates — and the plan's own test does this
`02-server-live-and-api.md:181`: `rec = {k: body[k] for k in ("seed","cfg","timesteps","description","text") if k in body}`
makes both optional; Task 6's happy-path test calls keep with only `{file, seed, cfg, timesteps}` (`02:689-690`).
The resulting `gen.candidates[cN]` then lacks description and text, so the kept candidate cannot be regenerated —
the exact promise spec goal 3 and risk 4 hinge on, one slice after we learned the 12 pilots are unreproducible
for precisely this reason. The server has both values at hand (manifest text, overrides-or-manifest description)
and should backfill them or 400.

### 1.6 No catch-all for non-`ApiError` exceptions — bad bodies drop the connection instead of returning JSON errors
`Router.dispatch` catches only `ApiError`; `app.py._api` has no try/except. Concrete triggers in the plan's own
code: `clone.generate` indexes `body["options"]`, `o["cfg"]` etc. (`02:471-472`); `fx.apply_to_take`'s
`subprocess.run(timeout=120)` raises uncaught `TimeoutExpired`. Under `BaseHTTPRequestHandler` these kill the
handler thread — the client sees a connection reset, not an error message, undercutting the Review Focus
promise that failures are *shown*. The existing `live_backend.py:82-83` wraps everything and returns
`{"error": ...}` with 500; one `except Exception` in `dispatch` matches that.

## 2. Spec/plan drift (record or reconcile)

1. **Model-status polling contradicts spec §3.4, unrecorded.** Spec: health is "polled while a live control is
   visible". Plan: `ModelStatus` sits in the always-rendered `AppShell` and calls `model.start` on mount
   (`04:308`) — polling every 5 s for the whole session on every view. Reasonable design (health is cheap and
   never touches the GPU), but it's a deviation and, unlike "loading shown as down", not recorded in the Global
   Constraints.
2. **Status dots replaced by group headers, unrecorded.** Spec §3 (line 128) specifies per-speaker status dots
   in a sidebar; the plan renders a grouped full-page list with section headers instead (`04:462-491`). Same
   information, different presentation — fine, but say so.
3. **Spec §5.1 route table is stale post-decision**: `POST /api/fx/assignments` is still described as "label
   map and speaker presets" though the label map is now studio-internal and assignments-writing is a later
   slice; `GET /api/model/health` still lists `down/loading/ready/busy` though the plan folds loading into down.
4. **Spec §4's table still lists `pasqal_lab/takes.json, profiles/*.json` as "existing state the app
   reads/writes"** while the paragraph below correctly says the directory doesn't exist. Delete the row.
5. **Overview "Self-Review / Placeholder scan" is inaccurate both ways**: it counts two fix-notes ("FXLAB
   parents index", "unused import in fx.py") that appear to be already-resolved in the printed code (the FXLAB
   line at `02:549` is correct `parents[3]` with an explanatory comment), and misses the `DesignState` export
   note at `03:400-403`. For a plan meant to be executed checkbox-by-checkbox by an agent, stale fix-note
   references are a real hazard — the executor may "apply" a fix that's already applied.

## 3. Nits

- `SpeakerView` loads only in `onMounted` (`04:937`) with a `:slug` prop route (`03:146`): Vue Router reuses
  the component on same-route param changes, so future speaker→speaker navigation (the spec's sidebar IA
  guarantees it) will show stale data. Latent today; a `:key="$route.fullPath"` or `watch(() => props.slug)`
  now is cheaper than debugging later.
- Narrator appears as a "real" speaker with an empty clip list: it's one of the 23 `prompts.json` speakers but
  has zero `catalog.json` entries (its curated prompts reference `bg3_narrator_*` events), so `_clips` returns
  `[]` though wavs exist. Harmless; deserves an explicit decision.
- Unlocked read-modify-write of `takes.json`/`audit.json` under `ThreadingHTTPServer` — inherited from the old
  servers, single-user, but this is the one place a per-file lock is cheap.
- `sys.path.insert` of `tools/voice_design` in `studio_server/design.py` (`02:130`) makes any future absolute
  `import design` resolve to the wrong module; `importlib.util.spec_from_file_location` avoids it.
- `GET /api/speakers/{slug}/takes` returns `200 []` for unknown slugs while every sibling 404s.
- `VoiceProfile.notes` exists end-to-end but is never written (no UI, `saveProfile` doesn't send it) — worth a
  sentence so nobody thinks it's wired.
- `spread.ts` (Task 13) is missing from Task 13's Files list and the overview File Structure; `spreadPick`'s
  doc ("50 to 220 characters") disagrees with its exclusive bounds.
- `runBatch`'s `onTake` is typed `(t: Take) => void` but receives an async callback fire-and-forget
  (`03:653,679` vs `06:625-634`); type it `void | Promise<void>` if ordering matters.
- Pinned web versions (Vite 5, Vitest 2, TS 5.6…) are mutually compatible but ~2 years old by now; fine for a
  local tool, make it a conscious choice.

## 4. False alarms checked and cleared

Two findings from the review passes did **not** survive direct verification — recorded so nobody "fixes" them:
- The `ClipCompare` `playing.value` template bug does not exist: the code block (`04:216`) correctly compares
  `playing === c.path` and line 234 explains the ref-unwrapping reasoning explicitly.
- The `fx_apply.py` `FXLAB` path is correct (`parents[3]`, `02:549`), as is the `parents[4]` math for the
  voice_design path insert (`02:130`). The overview's placeholder scan referencing an FXLAB fix is stale
  (see 2.5), not the code.
- `Take.seed: number` is correct: the real backend always returns an int
  (`live_backend.py:37,60` — `int(seed)` or `randrange`).

## 5. What the plan gets right (verified, not skimmed)

- **Backend contract is exact**: design/clone request fields, seed semantics (`""` → random 31-bit, else
  `int(seed)`), `reference_wav` under `data/`, continuation via `prompt_text`, response shape — all match
  `live_backend.py` line for line.
- **audit.json writes are byte-compatible** with the old page: `apply_verdict`/`apply_order`/`keep_candidate`
  are imported verbatim from `audit_server.py:86-123`, so both apps genuinely coexist (spec goal 5).
- **Real data shapes are handled**: bare-string candidates, missing `gen` → "no recorded seed" chip,
  accent-only verdicts, empty `order`, `pick: null` — the plan's parsers tolerate all of it, and the smoke-test
  numbers (35 speakers, Pasqal 45 clips / 844 lines, Vigdis 6 candidates) reproduce against the real files.
- **Route table ↔ typed client ↔ forward consumers**: Task 6's routes match Task 7's client method-for-method;
  every `SpeakerContext` member used in Tasks 12–14 exists in Task 11 with matching signatures; `runBatch` args
  match between Tasks 8 and 14.
- **Seed policy implemented as specified**: one seed per line shared across sources, tested (`03:495-505`);
  blank → random, typed → pinned; live-kept candidates record `gen` in the same shape `design.py` writes.
- **Offline behavior is clean**: speakers list and speaker-page loads never touch live routes; Generate/Keep
  are gated with stated reasons; FX apply is correctly not model-gated.
- **Review Focus coverage is real**: slug collisions, bad paths at every boundary, model-dies-mid-batch at
  three levels, corrupt `takes.json` reported not overwritten, empty states, large-list cap — each has the
  promised test.
- **The `/health` busy addition is safe** for existing consumers (Pasqal page reads only `h.ok`; the audit page
  never polls health) — verified, though the backend's module docstring should be updated too.
- **The M1 pause is well-formed**: manual start commands are printed (the `run.sh` reference is explicitly
  flagged as not-yet-existing), the handover reminder about writing to real `audit.json` is present, and the
  gate (user auditions 12 pilots) is the right risk to retire first.

## 6. On the execution-mode question

The plan's author recommends native execution (one builder, one reviewer at the end) over subagent-driven
(per-task builder + reviewer). This review's evidence supports **native, with two conditions**:

1. The shared-interface risk that argues for one context is real — but the defects found above are
   integration-level (Task 15's expectations vs real data, TakeRow vs server semantics), i.e. exactly the kind
   a single context *misses* because it wrote both sides. So: fix sections 1–2 in the plan text first, then
   keep an independent review at M1 and after Task 15 rather than only at the end.
2. The plan's self-review claims ("type consistency verified", "placeholder scan clean") proved partially
   inaccurate. Treat all remaining self-review assertions as unverified hints, not facts.

The stdlib-over-FastAPI decision is adequately justified in spec §5 (threaded server answers the concurrency
concern; ~20 routes; swappable later behind the route table). The "uvicorn failed on missing click" rationale
is an environment quirk rather than a real barrier, but the decision stands on its other merits. No objection.
