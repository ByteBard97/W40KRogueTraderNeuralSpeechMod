# Review: Voice Studio design spec (2026-10-09)

Reviewer: Kimi. Method: read the spec in full, then verified every checkable claim against the working tree
(code, data files, handoffs, git status). Findings are concrete with file refs; sections that check out are
marked as such.

**Overall verdict: the spec is well-founded and the architecture is sound, but it contains four factual errors
in the data-model section that matter (two of them change the design), one invented justification ("the
project's Vue conventions" — none exist), and several stale numbers. None of these are blockers; all should be
corrected before implementation starts, because sections 4 and 7 will be read as ground truth by whoever builds
slice 1.**

---

## 1. Factual errors that change the design

### 1.1 `batch.py` does not read a "label-to-preset map" (spec §T4, §4) — design error

Spec §T4 says FX authoring outputs "a global preset library plus a **label-to-preset map** for the harness's
effect labels (`machine`, `vox_channel`, …). The map is what `tools/fx_lab/batch.py` needs
(`data/fx_lab/assignments.json`)".

That is not what `batch.py` reads. `tools/fx_lab/batch.py:7,122,155` expects exactly:

```json
{"speakers": {"<speaker name>": ["<preset>", ...]}, "lines": {"<guid>": ["<preset>", ...]}}
```

Per-line beats per-speaker; multiple presets chain in series. There is no label/tag notion anywhere in
`batch.py` — tags exist only inside `tools/fx_lab/scenarios.json` entries. The harness's effect labels do exist
(`data/npc_profile/roster_35b_all.json` entries carry `fx[]` tags), but nothing maps them to presets today.

So the spec promises a contract with `batch.py` that doesn't exist. One of two things is true, and the spec
must say which:

- **(a)** `batch.py` will be extended to resolve label→preset→speaker (currently unstated work, and arguably in
  scope since §4 lists `assignments.json` as "the format `batch.py` already reads"), or
- **(b)** the label map is resolved at assignment-writing time (the studio expands labels into per-speaker /
  per-line entries when it writes `assignments.json`). This is simpler and keeps `batch.py` untouched —
  recommended — but then the "label-to-preset map" is studio-internal state, not the `assignments.json` format.

### 1.2 Existing candidates have no recorded seeds (spec §4, §T2) — reproducibility claim is false for current data

Spec §4 claims `design_manifest.json` has "`gen` (seed/cfg/steps per candidate)", and §T2 says kept candidates
"record seed, cfg, timesteps and description so they can be regenerated".

The real `data/voice_design/design_manifest.json` (12 NPCs) stores candidates as **bare filename strings**
(`"c0.wav"`…). No `gen` block, no seed/cfg/steps anywhere in the file. `tools/voice_design/design.py:44-60,110-113`
does now record per-candidate seed/cfg/timesteps (`seed_for`, `seed_all`, `manifest.gen.candidates`) and its
docstring (`design.py:10`) even warns "clips from before seeding was added have no entry" — but **all 12
existing NPCs predate that**. Combined with risk 3 (seed reproducibility unverified on the real model), the
honest statement is: *for the 12 pilot NPCs, the WAVs are the only reproducible artifact; regeneration is
already impossible.* The app should visually distinguish candidates with and without recorded generation
params, and the spec should stop implying the current manifest carries them.

### 1.3 There is no existing Pasqal data to import (spec §4, §7, risk 4)

`data/pasqal_lab/` **does not exist** — no `takes.json`, no `profiles/*.json`. The schemas exist only as code
in `tools/pasqal_lab/server.py:9,30,90` (written defensively if present). The Pasqal lab was built but never
used; the only real Pasqal artifacts are the 12 curated wavs in `data/voices/prompts/Pasqal/`.

Consequences: the "one-time import of existing Pasqal data" in §7 is a no-op; risk 4 ("careful one-time
import") is moot; and the "only intentional schema change" framing in §4 overstates a migration that is
actually just "start writing to `data/studio/`". Good news — but the spec should say so, because a reader will
otherwise plan for a migration that isn't needed.

### 1.4 `fx_apply.py` lives in `pasqal_lab`, not `fx_lab` (spec §5, §7)

The architecture diagram says the API server "runs FX via `tools/fx_lab/.venv-fx (fx_apply.py)`". The venv is
right (`tools/fx_lab/.venv-fx/` exists, has dawdreamer), but the script is
**`tools/pasqal_lab/fx_apply.py`** — its own docstring says to run it as
`tools/fx_lab/.venv-fx/bin/python fx_apply.py --in … --out … --preset …`. Slice 1's "FX applied through the
existing `fx_apply.py`" therefore depends on a file inside one of the two tools slice 1 is replacing. It should
be moved to `tools/fx_lab/` (or into the studio) as an explicit step, not discovered mid-implementation.

## 2. Factual errors that don't change the design (correct anyway)

- **Stale headline numbers (§1.1).** The 15,296 / 6,212 / 9,084 split matches `TODO.md`'s pre-narration-fix
  accounting. The live plan file (`data/render/jobs.jsonl`, regenerated 2026-10-08, 26,322 jobs) shows
  **12,918** priority-3 lines: 6,201 named-speaker lines from exactly 299 speakers (holds up), and **6,717**
  unnamed (not 9,084 — ~2.4k were re-planned as narrator per `TODO.md:51`). The plan is unaffected; the spec's
  "biggest block" framing still holds. Also note `TODO.md` itself is internally inconsistent (11,051 vs 10,966
  replaced); the real export index has 11,051 entries.
- **Port table (§1.2).** The spec's ports match how the pages are *actually run* per the handoffs
  (match_review on 8920, queue on 8950, render audit on 8951), but the **code defaults differ and collide**:
  `match_review.py:97` defaults to 8913, `render_corpus/audit_server.py:222` also defaults to 8913, and
  `queue_server.py:123` defaults to 8920 — double-booked with match_review's run port. The handoffs worked
  around this by overriding ports. Worth a footnote: the informal port registry is itself evidence for the
  spec's §1.2 problem statement, and the new app should register 8930 somewhere durable (8930 is genuinely
  free today — verified).
- **"Each with its own audio player" (§1.2)** — `match_review.py` is text-only, no audio element. Trivial.
- **"Mock model backend … as was used for the live-design and Pasqal pages" (§8)** — there is no mock backend
  in those pages' tests. `tools/pasqal_lab/tests/test_pasqal_lab.py` (29 lines) never touches the backend;
  `tools/voice_design/tests/test_voice_design.py` (113 lines) tests pure functions. The mock backend the
  testing section relies on is **new work**, not a reuse of an existing pattern.
- **"The audit page is at 315 lines and already strains" (§1.2)** — exactly 315 lines, confirmed, but 315
  lines is tiny; "strains" is asserted, not demonstrated. The stronger justification for the app is the one
  already in §1.2: five tools with five state files and no shared notion of a speaker. Lead with that.

## 3. The "project's Vue conventions" do not exist (§5, §6)

Spec §6 says the frontend follows "the project's Vue conventions (thin views, reusable components, composables
own state/side effects, typed `InjectionKey` context …, files under 500 lines)". There are **no Vue conventions
in this project**: no `package.json`, no `vite.config.*`, no `tsconfig*.json`, no `*.vue` anywhere outside
Python venvs, and the only markdown hits for vue/pinia/vite are this spec itself. The actual, demonstrated
convention is "single-file vanilla HTML+JS page, stdlib Python `http.server` backend, no build step" — nine
pages of it.

Vue 3 + TS + Vite + Pinia may still be the right call — the app is genuinely bigger than any existing page,
the shared `ClipCompare`/`useSpeakerContext` reuse argument is real, and the GPU-offline requirement means a
real client-side app rather than server-rendered pages. But the spec must argue it on those merits, not as
conformance to an invented standard, and it must own the costs explicitly:

- first Node toolchain in a Python repo (a second dependency universe to keep working);
- every future session needs `npm install` + Vite dev server or a prebuilt bundle checked in / built on demand;
- the rules in §6 (500-line files, no magic numbers, injection keys) will be *set by this project*, not
  followed from it — say that.

Worth considering and explicitly rejecting (or accepting): a middle path of Vue via ESM CDN with no build
step, which preserves the project's no-toolchain convention at the cost of TS and SFCs. Given how much
listening UI is left, TS + Vite is defensible — but make it a decision, not a citation.

## 4. Confirmed correct (no action needed)

Verified against the tree and found accurate:

- `audit.html` = 315 lines, vanilla JS string templates, port 8907; pasqal_lab 8910; fx_lab 8908.
- FX Lab: exactly **77 `hslider` controls** in `tools/fx_lab/faust/chain.dsp` and **23 blocks** in the GROUPS
  array (`tools/fx_lab/index.html:172-173`).
- AIVO bank ~38,000 clips (38,031 per `TODO.md:13`); Pasqal 45 clips / 12 curated
  (`data/voices/summary.md:20`, `data/voices/prompts/Pasqal/` = 12 wavs, all `ok: true`).
- 277 matches / 25 flagged — verified by running `match_review.py:build_rows()`. (Coincidence to note: the 25
  *flagged* matches ≠ the 25 *saved decisions* in `match_decisions.json`, which are 17 accept / 8 reject and
  cover only the flagged rows.)
- `live_backend.py` on 8909: VoxCPM2-only, one generation at a time (`LOCK`, `:29`), seed genuinely plumbed
  (`seed_all` immediately before `model.generate` inside the lock, `:53-55`; blank seed →
  `SystemRandom().randrange(2**31)`, `:36-37`). The "unchanged backend" plan is viable.
- Continuation-mode echo warning (§3.1) is accurate in substance: `tools/tts_engines/voxcpm2.py:30-37`
  documents the reference clip being prepended; mode is off unless `prompt_text` is sent. (Minor: there is no
  parameter *named* "continuation" — the backend route takes `prompt_text`. Align the profile schema's
  `continuation` field name with the backend or document the mapping.)
- `data/render/jobs.jsonl` (26,322 jobs) and `data/render/export/index.json` (11,051 entries) exist at the
  spec'd paths with the spec'd fields; roster file has gender/species/age/confidence/fx tags as claimed.
- `data/fx_lab/assignments.json` indeed does not exist and nothing produces it (spec's claim confirmed —
  modulo §1.1 above on what it should contain).
- `plan.py` consumes prompt banks, not profiles — so §T6's "wiring consumers is outside this spec" is
  internally consistent.
- Port 8930 is free; nothing in the repo references it.
- The goal-4 offline split (model-status store gating only live controls) is consistent with how
  `live_backend.py` actually behaves (separate process, `/health`).

## 5. Design-level concerns

1. **Slice 1 is still large.** It bundles: new API server, new Vue app + build + tests, five-section speaker
   page, live design, drag ranking, FX application, profiles, and a (moot) import. Meanwhile the handoff
   state (`HANDOFF-2026-10-09-1146.md:42`) says **the user has never listened to the 12 pilot designed
   voices** — the single gate on the entire voiceless-NPC track. Consider a walking-skeleton milestone inside
   slice 1 that puts exactly that audition loop (speakers list → designed source → ClipCompare → verdict
   written to `audit.json`) in front of the user first, before live design, FX, and profiles exist. The risk
   this spec is best placed to retire is "the designed-voice approach doesn't sound right", and slice 1 as
   ordered retires it last.
2. **Where do the other 287 speakers come from?** `design_manifest.json` has 12 NPCs; the named-speaker LLM
   pass that would produce descriptions for the 299 has not run, and nothing consumes `match_decisions.json`
   yet. The spec's T2 flow assumes descriptions exist. State explicitly: description generation is out of
   scope but a prerequisite; the Speakers list must handle "no description yet" as a first-class state (the
   status dot taxonomy — no voice / has source / profile saved — doesn't cover it).
3. **Concurrency is unspecified.** A proxied clone/design generation runs tens of seconds under a backend
   lock. If the studio API server is single-threaded, `/api/model/health` polling and `/file` audio serving
   stall behind it — exactly the "never interrupt the user's place" goal (§1.3) broken by construction. One
   line in §5 (async framework or `ThreadingHTTPServer`) closes this.
4. **The FX Lab bridge modifies a page the spec says stays untouched.** §6's iframe + `postMessage` bridge
   ("load clip, save preset name") requires the existing `fx_lab/index.html` to gain a message listener and
   accept cross-origin messages from :8930. That's a change to an old page during the "don't disturb" window —
   fine, but list it as such.
5. **Offline story for slice 1 is thin.** Goal 4 (work offline from the model) is real for ranking/comparing,
   but slice 1's centerpiece — live design — is precisely what doesn't work offline, and for the 12 pilot
   NPCs the candidates were batch-generated, so even "kept candidate" state is sparse (`audit.json` has 1 NPC,
   no picks, only `accent` annotations — no `fit`/`reject` keys exist in real data yet). The ranker schema
   (accent/fit/reject) is therefore unvalidated by use; expect it to change on first contact.
6. **VoiceProfile naming drift.** `options.use_instruct`/`continuation` vs backend's
   `instruct`/`prompt_text`; `options.seed` (single) vs the per-line seed policy in §3.1 (one seed per line,
   shared across sources; blank → random per line). The profile should store a seed *policy*, not a seed —
   the current schema invites a bug where a saved profile silently pins one seed across all lines.
7. **Sequencing risk kept implicit.** Slice 1 can be "done" while nothing in the render path consumes
   profiles, match decisions, or pool assignments (all explicitly out of scope). That's acceptable scope
   fencing, but the spec should name the follow-up specs (plan.py profile consumption, match-decision wiring,
   batch.py assignment consumption) so "done" doesn't quietly mean "inert".
8. **Where does the app live?** §6 shows a `src/` layout, but repo-root `src/` is the C# mod projects.
   Presumably `tools/voice_studio/` — say so, including where the built bundle and its Python server sit.

## 6. The spec's open questions — reviewer opinions (requested in §9)

- **API framework: FastAPI.** The stdlib convention made sense for single-route pages; this app has ~20
  routes with typed bodies, a long-polling proxy, and a TS client that wants a generated schema. FastAPI +
  pydantic + uvicorn gives validation and OpenAPI → typed client generation, and async handles finding 3
  above for free. The project already maintains several venvs, so one more pinned venv is not a new kind of
  burden. Stdlib would spend its savings re-implementing validation.
- **Pool assignment policy: automatic with exception queue + spot check (the recommended option).** 9k–15k
  lines cannot be hand-approved by one listener; the harness already emits per-axis confidences
  (`conf{gender,species,age,fx}` in `roster_35b_all.json`) which is exactly the exception-queue signal.
  Requirement: record provenance per line (`auto` vs `override`, plus the confidence at assignment time) in
  `pools.json`, so a later harness re-run can diff rather than silently reassign user decisions.

## 7. Minor notes

- §7 says old pages "keep their current ports" for out-of-slice tools — true, but see §2: two pairs of
  *defaults* collide (8913 ×2, 8920 ×2). If the studio ever offers "open old page" links, use the handoff
  ports, not the code defaults.
- The spec's risk list is good; add risk 1.2 above (existing pilot candidates unreproducible) explicitly, and
  drop risk 4 (no Pasqal data exists to migrate).
- `audit.json`'s real contents (1 NPC, no picks) mean the "don't disturb existing state" goal is cheap to
  honor — a backup-before-write test (§8, good idea) is sufficient; no dual-write choreography is needed.
