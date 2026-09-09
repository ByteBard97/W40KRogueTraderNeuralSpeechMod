# Emotional expressiveness: synthesis and action plan

Written after cross-referencing 8 independent research reports against primary sources
(Resemble AI's own `added_tokens.json`, HF discussion threads, and the QwenLM/Qwen3-TTS repo).
Where reports disagreed, this document states which side is verified and why. Companion to
`emotional-expressiveness-prompts.md` (the research prompts that produced those reports).

## Diagnosis

The flat delivery isn't a ceiling on what neural TTS can do — it's two dead controls and one
wrong assumption about the reference clip.

1. `annotation_bridge.py`'s `for_chatterbox()` scales an `exaggeration` value into a 0.3–0.8
   range on every line. On Chatterbox-Turbo, `exaggeration` and `cfg_weight` are silently
   ignored — confirmed directly by Resemble AI staff on the model's HF discussion tab, and by
   the model's own config (`emotion_adv: false`). Every line synthesized so far has run with
   zero exaggeration signal, regardless of the number in the code.
2. The bracketed emotion tags (`[angry]`, `[dramatic]`, `[sarcastic]`, etc.) *are* real trained
   tokens — verified directly against `added_tokens.json` (19 tokens, IDs 50257–50275) — but
   Resemble only officially documents 9 of them (the non-verbal sound-effect tags: `[sigh]`,
   `[gasp]`, `[laugh]`, etc.) and the other 10 emotion/style tags are reported "hit or miss" by
   the community. They're a real but unreliable lever, not a fake one.
3. Every character's reference clip is currently chosen by `tools/build_prompt_banks.py`'s
   `score_clip()` purely on audio-quality heuristics — never on emotional content. In zero-shot
   cloning, the reference clip's own prosody is a strong prior on the output; conditioning an
   `[angry]`-tagged line on a calm, clean reference clip fights the tag rather than supporting
   it. This is documented behavior in Chatterbox and reported the same way for every other
   zero-shot engine checked (Qwen3-TTS, XTTS, Zonos).

None of this required inventing a better model. It required using the model correctly.

## Constraint that reshapes everything downstream

Synthesis is **live, per-player, local** — never pre-rendered and shipped. Each player extracts
their own voice references from their own copy of the game via an opt-in local tool; the mod
ships code and metadata (annotations, lexicon), never audio, and never a model trained on the
game's voice actors. This rules out anything that means shipping dev-trained model weights or
baked audio, and it means every proposed engine or technique has to run acceptably on a
typical player's GPU, not just the dev machine, within the existing graph-lookahead prefetch
window.

## Stage 1 — Fix the dead controls (do this first, this week)

Switch the sidecar's Chatterbox engine from `ChatterboxTurboTTS` to the original `ChatterboxTTS`
(0.5B). This alone re-enables `exaggeration`/`cfg_weight`, which is the single highest-leverage
change available, and it costs nothing on the Windows-distribution side — the original model has
its own official ONNX export (`onnx-community/chatterbox-ONNX`, confirmed live) with
`exaggeration` exposed as a graph input.

Concrete changes to `src/TtsSidecar/annotation_bridge.py` and `tools/tts_engines/chatterbox_turbo.py`
(or a new `chatterbox_base.py` engine adapter):

- Map `intensity` (0–1) → `exaggeration` in **0.5–1.0**, not 0.3–0.8.
- Map `intensity` → `cfg_weight` **anti-correlated**, roughly 0.4 down to 0.2 (high exaggeration
  needs low cfg_weight to avoid rushed, garbled delivery — this pairing is the one thing every
  report agreed on without exception).
- Add `temperature` 0.8–1.0 on emotional lines (0.6 or default on neutral/expository lines).
- Fix `_CHATTERBOX_TAGS`: it currently has no mapping for `commanding` or `pleading` at all —
  those two emotions silently get no tag today. Give them one (e.g. `commanding` → `[angry]` +
  capitalization, `pleading` → `[crying]` or `[fear]` + ellipses — see Stage 2's reference-bin
  scheme for a cleaner fix).
- Add text-level scaffolding: capitalize 1–3 key emphasis words per line, use em-dashes for
  dramatic pauses and ellipses for hesitation, on emotional lines only (never touch the neutral
  majority — over-applying this reads as parody, per multiple community reports).

**Test before moving on:** re-synthesize the ~30–50 flattest-sounding lines from your existing
annotated batch (pull a stratified sample across `angry`/`dramatic`/`sarcastic`/`commanding` —
the emotions most affected by the dead exaggeration knob) and listen. If they're still flat, the
mechanism analysis above is wrong somewhere and Stage 2+ should be re-sequenced ahead of more
engine work; if they're audibly better, proceed.

## Stage 2 — Emotion-matched reference clips

Replace `build_prompt_banks.py`'s pure quality-ranking with an emotion-aware selection. Don't
try to build 12 separate clip sets per character — cluster into 4 acoustic bins, which multiple
reports converge on independently:

- **Bin A** (aggressive): angry, commanding
- **Bin B** (agitated): fear, pleading, surprised
- **Bin C** (subdued): sad, whisper
- **Bin D** (conversational/dynamic): neutral, sarcastic, dramatic, happy, amused

For each character, pull 2–3 candidate clips per bin from the existing extracted VO
(`data/voices` / the 5,188 speaker-attributed WAVs already on disk) using a cheap heuristic pass
first — pitch mean/variance and RMS energy from the existing `score_clip()` pipeline can
approximate arousal without a full SER model — trim to 6–10 seconds (Chatterbox hard-truncates
conditioning at 6s/10s anyway, so longer clips waste nothing but also gain nothing), and route
each line's synthesis to the bin matching its annotated emotion. This is one-time curation work
that happens as part of the *existing* per-player local extraction step — it doesn't change the
distribution model at all.

**Test before moving on:** pick 10 lines per bin, synthesize each once with the current
"cleanest clip" reference and once with the bin-matched reference (same text, same tags, same
exaggeration), and blind-compare. This isolates the reference-clip effect from the Stage 1
parameter effect, which matters because several reports' recipes conflated the two.

## Stage 3 — Give yourself a real metric before doing anything else

Right now "is this more emotional" is judged by ear, which doesn't scale and doesn't survive
disagreement between reports. Add to the eval harness (`data/bakeoff/`, `tools/listening_test/`):

- **A speech-emotion-recognition (SER) score**: run a pretrained classifier (emotion2vec / 
  emotion2vec+ is the most-cited choice across the literature, MIT-licensed) on generated audio
  and record the predicted probability for the *target* emotion. This is a per-line, cheap,
  automatable number.
- **Prosodic features as a secondary, explanatory metric**: F0 semitone standard deviation and
  RMS energy dynamic range via `parselmouth`/`librosa`, tracked per emotion bucket. This tells
  you *why* a config change helped, not just *whether* it did.
- **Calibration expectation, so you don't chase a false target**: published data shows even real
  human actors are only correctly identified on their intended emotion 40–70% of the time by
  listeners. Don't treat anything short of "obviously, unmistakably that emotion" as a failure —
  treat your own blind-listening-test pass rate as the real bar, with the SER score as a fast
  proxy for iterating between listening-test rounds, not a replacement for it.
- **Demote WER and ECAPA similarity to guardrails, not objectives.** Emotional delivery costs
  intelligibility — that's expected and acceptable per your stated priority. Use them as a floor
  ("did the words survive") rather than something to optimize alongside expressiveness.

Do this now, not after Stage 4, because every subsequent decision (was the engine swap worth it,
did the reference-clip change help, is a second engine actually needed) needs this to be
answerable in something better than vibes.

## Stage 4 — Only if Stage 1–3 still don't clear your bar

**Correction from later research:** Qwen3-TTS is disqualified for this stage entirely, and not
for a licensing or ONNX reason — no checkpoint in the family combines cloning with
instruction-following. `Base` clones your reference but ignores `instruct`; `CustomVoice` and
`VoiceDesign` follow instructions but only on 9 fixed preset voices, never a reference clip you
supply. This is confirmed architecturally (official model cards, a maintainer-adjacent koboldcpp
discussion, an mlx-audio issue showing the code path ignores supplied clone refs when using
CustomVoice) — it is not fixable by picking a different checkpoint. Qwen3-TTS still has one
legitimate use in this pipeline: as a **reference-clip factory**. `CustomVoice`/`VoiceDesign` can
synthesize a plausible example clip in a given emotional register on demand, which is useful for
Stage 2's per-bin reference clips on any character/bin combination where the real extracted game
audio doesn't have a good example (e.g. a companion with no recorded panic line).

Re-run a small bake-off against the *fixed* Chatterbox baseline (not against the old
Turbo-with-dead-parameters baseline — that comparison is meaningless now), on a fixed ~100-200
line probe set spanning all 12 emotions and both intensity extremes, scored by the Stage 3
metric plus a blind listening pass. Candidates, in order of fit:

1. **Fun-CosyVoice3-0.5B-2512(_RL)** (Apache 2.0) — the only model whose architecture actually
   matches this pipeline's shape: `inference_instruct2(text, instruct_text, prompt_wav)` clones
   from your reference clip and drives delivery from the annotation's `instruct` field in one
   call. Mechanically, it keeps only the reference's *timbre* and discards its *prosody*,
   replacing delivery entirely with what the instruction specifies — which directly sidesteps the
   reference-clip-prosody-cap problem from Stage 2, from a different angle than emotion-matched
   clip binning. The catch: no full ONNX export exists (the LLM stage is PyTorch/TensorRT-LLM
   only; a community export covers just the Flow+HiFT half on DirectML), so it's a Linux-sidecar
   engine only — ship Windows via Chatterbox regardless. English dramatic-delivery quality is
   thin evidence (mostly Chinese-language instruct examples in the wild; one systematic community
   reviewer rated it 3.5/5 expressiveness but only 2.0/5 realism, versus Chatterbox's 4/5 and
   4.5/5 once tuned) — validate this specifically in the bake-off rather than assuming it.
2. **VoxCPM2** (OpenBMB, Apache 2.0, 2B) — also does clone + free-text style instruction in one
   call ("Controllable Cloning"), and posts the best measured English instruction-following score
   of any open model checked (InstructTTSEval-EN APS 84.2, ahead of CosyVoice3 and every Qwen3-TTS
   checkpoint), plus the fastest RTF of the group (0.13–0.30 on an RTX 4090). Real caveat, from
   the authors themselves: output style/quality varies run-to-run enough that they recommend
   generating each line 1–3 times and picking the best — budget for that if you adopt it. ONNX
   export exists but is CPU-only today; no Windows/DirectML path yet.
3. **IndexTTS2/2.5** stays excluded, on firmer grounds than "non-commercial reference point": its
   license (the bilibili Model Use License Agreement) carries flow-down obligations that would
   attach to everyone who downloads your mod, not just a revenue/MAU threshold on your own use —
   treat it as fully excluded, not evaluation-only.
4. Verify Higgs TTS 2's actual license before spending any time on it — Boson AI's blog claims
   Apache 2.0 but the HF model card says "other"; unresolved as of this research.

Whatever wins, remember the constraint: it has to run acceptably on a typical player's GPU, not
just yours. If it doesn't, a per-line hybrid (fixed-Chatterbox for most lines, the new engine
only for lines above some intensity threshold) is the fallback, not a full swap — the annotation
schema already carries per-line emotion/intensity, so routing is just a lookup, not new
infrastructure.

### 4a — If you adopt an instruct-based engine: rewrite the `instruct` field generation

The annotation LLM's prompt currently produces clinical descriptions ("she says this
sarcastically, with a cold, mocking edge"). Evidence across multiple instruct-TTS benchmarks
says this under-performs: descriptive/clinical labels land the model in a broad, ambiguous
region of its conditioning space and it defaults toward neutral. What performs measurably
better is a physical, acoustic-parameter description — pitch direction, volume/energy, tempo,
phonation texture — written as if directing a voice actor's body, not naming their emotion.
Rewrite the annotation prompt to require: no clinical emotion labels, 20–35 words, one clause
each for volume/projection, pitch contour, pacing, and phonation texture, and keep it separate
from any inline paralinguistic tags (which go in the transcript text itself, not the instruct
field). This is a prompt-template change only — free, and worth doing regardless of which engine
you land on, since it also improves anything a `Qwen3-TTS`-class model does with the field you
already generate.

## Optional technique: sample-and-rerank

Generating N candidates per line and keeping the best (scored by the Stage 3 SER/prosody
metric) is a real, literature-supported technique for pulling expressive delivery out of the
low-probability tail of a model's output distribution. But cost it correctly: this runs on each
*player's* machine, once per line the first time their playthrough reaches it (then cached, per
the existing disk-cache design), not as a one-time dev-side batch. Budget N small (3, not 6+)
and restrict it to lines above some intensity threshold — most lines don't need it, and it has
to fit inside the existing prefetch window on ordinary hardware, not just yours. Treat this as a
polish pass to try after Stage 1–2 land, not a substitute for fixing the dead parameters first.

## Ruled out — do not revisit

- **Fine-tuning or LoRA-adapting a model per character on the extracted game VO, and shipping
  the resulting weights.** This is materially "distributing cloned voice data" regardless of
  whether it's framed as a checkpoint or an adapter — it's a reusable model capable of
  generating unlimited new speech in a real voice actor's voice without consent. The only
  version consistent with the project's distribution model (every player fine-tunes locally, on
  their own extracted audio, before playing) is impractical: hours of GPU training per
  character, times a dozen-plus characters, before anyone can start the game.
- **Any form of pre-rendering audio and shipping it as a mod asset.** Several research reports
  assumed this was the architecture and costed things accordingly (e.g. "run this as an offline
  batch job on your own GPU"). It isn't, and it can't be — see the constraint section above.

## Suggested order of operations, concretely

1. Switch to `ChatterboxTTS` base, apply the corrected parameter mapping and tag fixes (Stage 1).
2. Spot-check 30–50 flat lines by ear. If still flat, stop and re-diagnose before continuing.
3. Add the SER/prosody scoring pass to the eval harness (Stage 3) — do this in parallel with (1)
   if convenient, since you'll want it to judge (1) anyway.
4. Build the 4-bin emotion-matched reference clips for a handful of characters first (Stage 2),
   A/B against the quality-ranked clip on the same lines, confirm it helps before doing the full
   cast.
5. Run the existing blind listening test (already built, never run) against the Stage 1+2
   output vs. the original Turbo baseline — this is the real tiebreaker your own bake-off notes
   already flagged as outstanding.
6. Only then decide whether Stage 4 (a second engine) is worth pursuing, using the Stage 3
   metric plus the listening test to make that call on evidence rather than another round of
   research reports.

## Loose ends worth a quick check, not urgent

- Whether the official Chatterbox-Turbo ONNX export (`ResembleAI/chatterbox-turbo-ONNX`,
  confirmed live, four sessions matching the architecture already planned in `PROJECT_PLAN.md`)
  can be consumed directly for the Windows in-process backend instead of doing that export
  yourselves — check this before starting that spike.
- NVIDIA's ACE-for-Games "GGML Chatterbox" plugin as an alternate Windows deployment path
  (officially documented on docs.nvidia.com) — real, but NVIDIA-only, so it can't replace the
  ONNX Runtime + DirectML path if you want to support AMD/Intel players.
