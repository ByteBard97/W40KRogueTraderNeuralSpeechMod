# TODO: replacing the remaining AIVO audio

> **STAY ON TRACK (2026-10-08):** the FX / post-processing build is a detour. The main line is the voiceless NPCs:
> (1) audition the 12 pilot NPCs (:8907) -> (2) review match decisions (:8920) -> (3) wire them into `plan.py` -> (4) named-speaker pass + voice design -> (5) render priority 3.
> Return here when the FX work wraps up. Details in `memory/return-to-voiceless-npcs.md`.


Last updated 2026-10-07. This tracks the work between "11,051 lines swapped into the AIVO bank" and "every line has our audio".
`PROJECT_PLAN.md` has the architecture and history; this file is only what is left, in the order I'd do it.

## Where things stand

- 10,966 of the bank's 38,031 clips are replaced with our audio (VoxCPM2 / Qwen3-TTS), installed as a main bank plus two media-only side banks.
- The BG3 narrator render (4,304 lines) is merged and the rebuilt banks are installed. The user played 1 to 2 hours on the earlier build with no problems; the narrator build has had less play time.
- The other ~27,000 clips still play pas2k's Chatterbox audio:
  - 15,296 priority-3 conversation lines (6,212 from 299 named NPCs, 9,084 with no speaker at all).
  - 11,767 non-dialogue strings (codex, item and weapon text, epilogues, names) that are not in the render plan.
- The speaker/label harness exists and has been tested on ~25 conversations. It has not been run on the whole corpus.
- Nothing from this work is committed.

## 0. Bank in game: working, one optional check

- The user played 1 to 2 hours with the swapped banks and heard no silence, static or missing lines, and could not tell generated lines from the
  recorded ones. A broken PCM wem or side bank would have been obvious, so this is treated as working, not as a blocker.
- [ ] Optional, cheap: after a play session, compare the `ev_<guid>` events in `Player.log` with the swapped set to see which swapped lines were actually hit
      (19 of 86 distinct events were in the first log). Also keep an eye on RAM use in game.
- Rollback is in `soundbanks_disabled/` (`*.pre-bg3`, `.chatterbox-original`) if anything misbehaves later.

## 1. LLM harness and labelling (`tools/npc_profile/`)

Run the 35B first (about 3 to 5 hours for tier 1), then the 122B only on what is flagged.
Start command and flags are in `memory/npc-speaker-harness.md`. Do not use `-ub 1024 -b 1024` (it crashes).

- [x] Gold-set check (2026-10-07): ran the delivery stage on the 172 gold lines that are in the corpus (`data/npc_profile/seg_gold.jsonl`).
      Emotion match 0.349 versus 0.517 for the old labeller on the same lines. It labels 62 of 172 "dramatic" where the gold has 19 (gold is 78 neutral).
      Pace match is better (0.721 vs 0.628), intensity MAE slightly worse (0.169 vs 0.145). **Do not relabel short lines with it.**
      Only use it for the split decision and per-segment delivery on long lines.
- [ ] Shrink the speaker stage's output (only list per-line delivery/fx where it differs from the character baseline). Roughly halves the run.
- [x] Tier-1 run (2026-10-07/08): all 614 conversations through the 35B on the Windows 4070 (two workers), 0 failures, ~5.5 h.
      Results: `data/npc_profile/roster_35b.jsonl` + `roster_35b_b.jsonl` (merged copy `roster_35b_all.json`). 442 roster entries, 9,453 attributed lines
      (2,666 narrator, 4 unknown), 73 conversations flagged needs_review at threshold 0.8. A second worker gave only ~15% more throughput.
- [ ] Threshold audit: pick the audit threshold by checking a sample of flagged and unflagged conversations by hand.
- [ ] 122B pass on flagged conversations (measure its real tok/s on this machine first; the benchmark I found is for a 4080).
      Needs the GPU free of other jobs and plenty of RAM free (42 GB weights).
- [ ] `compare.py` 35B vs 122B, then a review page for disagreements (not built).
- [ ] Hand review of whatever remains. Known gap: a confidently wrong attribution is not caught by probabilities
      (e.g. `Trial_dialogue` lines 47 and 49 may not be Heinrix).
- [ ] Named-speaker pass: evidence files already exist (`data/npc_profile/evidence/`, 299 speakers). Upgrade `gather_evidence.py` to rank narration
      by voice/appearance words, write the prompt, run it, produce voice descriptions.
- [ ] Wire roster results into `plan.py`: new speaker identities, `known_as` mapping to existing voice banks, regenerate `jobs.jsonl`.
- [x] Narration fix in `plan.py` (2026-10-07): unquoted lines from `default_speaker`/`unit` now plan as narrator (2,381 lines). Dry run only; `jobs.jsonl` is NOT regenerated yet.
- [ ] Optional second 122B/35B look at multi-speaker conversations once any turn up (none found so far).

## 2. Text splitting and per-segment delivery

Only lines of 450+ characters with quoted speech are candidates: 564 in priority 3 (338 of them unnamed), 120 companion lines already rendered whole.

- [x] `segment.py` / `run_segment.py` built and tested (53 offline tests). On 15 long lines it split 4, sensibly.
- [ ] Run the 564 long priority-3 speech lines (about 35 minutes). Review every split plus the "torn about splitting" ones by hand.
- [ ] Renderer support for segments: render each segment, stitch with a short pause and crossfade, match loudness, re-anchor the reference per segment
      (VoxCPM2 drifts on long generations). Not written.
- [ ] Blind listening test: about 10 lines, whole versus split. If the seams are audible, do not ship splitting.
- [ ] Decide whether to re-render the 120 long companion lines if splitting wins.
- [ ] Sentence splitter edge cases (abbreviations, quoted speech inside quotes) once we see more lines.
- [ ] Do NOT relabel all 15,000 lines unless the gold-set check says the old labels are poor. It costs about 15 hours.

## 3. Voices for the priority-3 speakers

- [ ] Audition the pilot NPC candidates (`tools/voice_design/audit_server.py`, port 8907). The user has not heard them yet.
- [ ] Top ~80 named speakers (4,796 lines): design 6 candidates each from the harness descriptions, auto-score (accent hint, ECAPA consistency,
      clone test on 2 real lines), pick, `register.py`.
- [ ] Tail of ~170 minor speakers and the unresolved `default_speaker` lines: 5 to 14 generic voices by gender/age/species, not one per NPC.
- [ ] Machine voices (servitors, terminals) get a deliberately flat voice; accent control is weak, so check by ear.
- [ ] Theodora's apparition: her real voice (bank exists, 27 voiced lines) plus ethereal/monstrous fx. Her reference clips are calm; she may need an emotion-matched one.
- [ ] Re-run `plan.py`, then re-check the 5080 / 4070 split (the Mac mini is gone).

## 4. Rendering

Merge rule: **the first run directory with a guid wins** (`merge.py`), so list the newest runs first.

- [x] Plan for the 11,767 non-dialogue strings: `tools/render_corpus/plan_extra.py` -> `data/render/jobs_extra.jsonl` (2026-10-07). 11,206 jobs, ~20.4 h audio, narrator reference
      from `jobs_narr_bg3.jsonl`. Skipped: 361 "Placeholder", 161 ids like `B573`, 39 non-English. `category` field: sentence 4,215, quoted 4,428, short_name 2,512, long 51.
      Not rendered. Open: the 4,428 quoted strings are read by the narrator, so some should probably use a character voice; the 51 long ones (1,200+ chars) need splitting
      first; decide whether the 2,512 bare names ("Rocky World") are worth rendering. Run with `render.py --jobs data/render/jobs_extra.jsonl --name <run>`.
- [ ] Multi-speaker cues (several voices in one cue): annotations live in `data/npc_profile/segments.json` (guard: `tools/render_corpus/segment_annotations.py`; add with `add_segments.py GUID --file|--from-proposed`; `propose_segments.py` finds inline "Name:" labels). Plan with `plan_annotated.py` (own file `data/render/jobs_annotated.jsonl`, ids `<guid>~a<k>`), then `render.py --engine voxcpm2 --jobs data/render/jobs_annotated.jsonl --name annotated-seg` (needs the user's GPU go-ahead), `asr_check.py --run annotated-seg`, `stitch_mixed.py --jobs data/render/jobs_annotated.jsonl --runs annotated-seg --out annotated-stitched`, and when overlaying list `annotated-stitched` LAST in `overlay_export.py --overlay` (later runs win there; `merge.py` is the first-wins tool). 11 labelled cues annotated so far (WebwayGate Bridge/Lookout, Skeletons Scout 1/Lookout); the Stryx, Cassia_Q2 and Ulfar cases wait on the user's answers. Cues with no inline labels (nested quotes) are not detected yet.
- [ ] Render the 203 short narrator lines (qwen3, about 10 minutes on the 5080; Windows has only the VoxCPM2 env).
- [ ] Render priority 3 (about 52 hours of audio at RTF 0.32 on the 5080, slower on the 4070) and the non-dialogue strings (about 19 hours).
      Order: named speakers first, then non-dialogue strings, then generic voices.
- [ ] Redo any `too_long` takes (one narrator line was skipped by the merge).
- [ ] Rebuild and reinstall the banks after each batch (`tools/bnk_patch/patch.py`, game closed). The wem cache is keyed on wav mtime and size.
- [ ] Watch RAM: the bank set is already about 8.3 GB loaded; unmeasured in game.
- [ ] Do not start GPU jobs unasked. Another project (`superglue`) shares the 5080.

## 5. FX pipeline (post-processing)

The chain exists (`tools/voice_design/fx.py` + `dsp.js`): high/low-pass, drive, bitcrush, ring mod, tremolo, echo, reverse reverb, mix, speed.
`data/voice_fx/presets.json` and `library.json` are empty. The harness already picks from these labels, at most two per character or line:
`machine`, `vox_channel`, `helmet`, `ethereal`, `monstrous`, `cavernous`.

- [ ] Define each label as a preset and tune by ear on the audition page (labels only so far).
- [ ] Missing DSP: pitch and formant shift (matters most for `monstrous`, Orks, giants) and chorus/octave-down layering. Add to both `fx.py` and `dsp.js` and keep the parity test passing.
- [ ] Decide how two labels combine (run one preset after the other is simplest). The harness sorts them into a fixed order already.
- [ ] Intensity: low by default; heavy effects hurt clarity.
- [ ] `apply_fx.py` writes only processed speakers to `export_fx/`; the patcher needs a merged directory with processed lines winning over raw. Not written.
- [ ] In-game on/off toggle: bake raw and fx variants for the affected characters only, and a small patch to the event lookup. Runtime DSP is not practical
      on the Wwise path (Unity audio is disabled in Rogue Trader).
- [ ] Per-line fx from the harness (e.g. an ordinary person heard over a vox) is stored per line; the renderer/exporter does not use it yet.

## 6. Post-processing what is already rendered

11,051 lines are rendered and in the bank: companions (priority 0 and 1) and the narrator. They have no fx labels yet.

- [ ] Per-character fx for the named companions and narrator: about 25 speakers, so decide by hand (Pasqal machine-ish, psykers ethereal, and so on). **No LLM needed.**
- [ ] Per-line cues: scan the source text for explicit cues ("vox", "static", "helmet", "echoes", "whispers in your mind") and look at the hits.
      An LLM check on only those hits is optional; a full LLM pass over 11,000 lines is not worth it.
- [ ] Apply with `apply_fx.py` to a copy, listen, then rebuild the banks. The raw renders are never modified.
- [ ] Check whether any already-rendered long lines (the 120 companion ones) should be re-rendered split, if section 2 shows splitting helps.

## 7. Release (user-runs-the-pipeline plan, see `memory/release-plan.md`)

- [ ] Tell pas2k before anything ships. Our bank embeds their event structure and still carries their audio for unrendered lines.
- [ ] Package the pipeline: config of speaker to reference clip (users supply their own 10 to 20 second clips; none shipped), line manifest built from the user's own
      AIVO index (not shipped), hardware check, resumable generation, rollback command.
- [ ] Never ship BG3 audio or the cloned narrator. Pre-generated audio may be shared privately on request only, as a diff plus side banks, never pas2k's audio.
- [ ] README, Reddit, Discord and Nexus text, each run through the `humanizer` skill; AI disclosure in the first line.
- [ ] Check Nexus size limits and current AI-content policies, and Larian's fan-content policy, before posting.

## Known bad scene: Jae in the Footfall Liege conversation

- [ ] Jae's lines in the Vladaym/Liege scene (cues `6328405c-2613-46f7-9f70-c5d2d8d01678`, `3aea06fa-08a7-479e-beea-a7ab69ab5701`) play the original AIVO audio in a male voice, and the italic narration inside the same cue is voiced by the old narrator. Root cause (found 2026-10-11): these are `default_speaker` cues (no explicit speaker blueprint; the game substitutes whoever is speaking at runtime). `tools/build_conversations.py` `resolve_default_speakers` guesses them from the dialog's majority speaker (kind `unit_guess`, here Vladaym), but the game had Jae speaking (runtime target `PC_Human_Jae`, logged in `played.jsonl`). Scale: 1,831 planned cues are `unit_guess` guesses (1,319 already rendered, so some may be in the wrong voice) and 10,152 `default_speaker` cues are unresolved. Ideas: (a) have the exporter or the Dialogue Flag mod record the real speaker per cue at runtime and use that as ground truth for the plan, (b) treat cues whose dialog has companions present as ambiguous rather than guessing the majority NPC, (c) at minimum, re-check the `unit_guess` renders against `played.jsonl` targets. Also mixed lines (speech plus narration) are handled by the new segment pipeline (`tools/render_corpus/plan_mixed.py`), and Jae needs a proper female voice.

## 8. Housekeeping

- [ ] Commit the new code (nothing is committed; about 56 changed or untracked paths). No Claude attribution in commit messages. Do not push without being told to.
- [ ] Old render directories and `data/render/export.pre-bg3` can be cleaned up later, but only with an itemised, approved list (use `gio trash`, never `rm`).
- [ ] Keep `memory/` current when the plan changes (Mac mini is gone, the narrator banks are installed).
- [ ] `PROJECT_PLAN.md` is out of date about everything after the bake-off; update it when the pipeline settles.

## 9. Side project: texture sharpness and the game-driving bridge

- [ ] See `tools/atlas_upscale/TODO.md` (return script for the Topaz texture tests; MCP/HTTP bridge so Claude can screenshot and drive the game). Not part of the audio work.

## Open decisions

- Does splitting beat whole-line rendering by ear? (section 2 listening test)
- Relabel short lines or not? (gold-set check)
- 35B only, or 35B plus a 122B pass on flagged conversations?
- Generic voices: how many, and which genders/species?
- How do two fx labels combine, and what does each label actually do?
- Ship the BG3 narrator at all? Current plan: no, users supply their own reference clip.
