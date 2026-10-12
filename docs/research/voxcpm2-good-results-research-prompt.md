# VoxCPM2: getting consistently good, in-character cloned results — research agent prompt

One self-contained prompt below — copy the whole section into a research agent (Gemini/Claude/
Kimi deep-research or similar). It repeats project context so it stands alone.

## Shared background (for you, not required reading for the agent)

Fan-made TTS mod for a story-heavy RPG (Warhammer 40,000: Rogue Trader). Character voices are
zero-shot cloned from short reference clips (~2-30s) of that character's real in-game dialogue
audio. VoxCPM2 (`openbmb/VoxCPM2`, Apache-2.0) is one of two finalist engines in an internal
bake-off (the other is Qwen3-TTS Base) — it's currently the stronger performer overall (most
first-place picks in blind listening comparisons), and unlike Qwen3-TTS Base it has a real,
documented instruction-following channel: a free-text style/emotion description passed as a
`(...)` prefix on the target text, alongside `reference_wav_path` for the cloned identity
("Controllable Voice Cloning"). The problem isn't that it can't be expressive — it's getting that
expressiveness to land *consistently in-character* rather than either flat or over-the-top, and
avoiding outright identity failures (wrong voice entirely, not just wrong delivery).

Prior research already done in this project (checked directly against primary sources - the
official VoxCPM docs at `voxcpm.readthedocs.io` and real GitHub issues on `OpenBMB/VoxCPM`, not
just recalled or inferred), so the agent should NOT re-derive these from scratch:

- **Short target texts are an officially acknowledged instability.** The docs state directly:
  "the model was trained with a minimum audio length of around one second," and short inputs
  "may sound weak." This project independently found the same thing empirically — three separate
  short target lines (all under ~40 characters) produced the wrong voice entirely, not just a bad
  delivery, while longer lines using the same reference clips were fine. No documented workaround
  exists beyond expecting instability and retrying.
- **Stacking multiple emotional descriptors in one instruction is a documented anti-pattern.**
  The official cookbook warns: "adding too many complex voice instructions might spoil the
  broth," recommending concise, single-focus style modifiers. This project hit exactly this
  failure mode: an instruction stacking four descriptors (shaken / whispered / genuine dread /
  horrifying) made a normally composed, reserved character sound melodramatic and out of
  character. A toned-down, single-focus rewrite is the current fix in testing.
- **`cfg_value`** (classifier-free guidance scale, default 2.0, documented range 1.0-3.0) and
  **`inference_timesteps`** (diffusion steps, default 10, documented range 4-30) are real,
  documented parameters this project had never tuned before this research pass - only the
  general tradeoff is documented (stricter conditioning adherence vs. naturalness/speed), not
  specific guidance for reducing voice-identity drift. An initial informal test at `cfg_value`
  2.0/2.5/3.0 on a known-bad short line didn't show an obvious clean fix, but wasn't a rigorous
  study either - this remains genuinely open.
- **A real upstream bug exists matching this project's own reference-audio-echo findings on a
  different engine (Qwen3-TTS).** `OpenBMB/VoxCPM` issue #272 documents the tail of the
  reference audio leaking into the start of generated output (a chirp/click artifact). No full
  fix exists upstream; PCM trimming of the reference clip partially helped one reporter.
- **Run-to-run variance is real and expected**, not a project-specific problem - VoxCPM2's own
  team recommends generating 1-3 times and picking the best result, and is "actively working on
  improving controllability consistency" with no stated timeline. No parameter, seed-control
  trick, or automated best-take heuristic was found in official docs or issues - only blind
  manual retries.

**What's genuinely unresolved, and the actual point of this prompt:** does the reference clip's
own delivery style/prosody meaningfully shape the output's expressiveness the way it's been
confirmed to for Qwen3-TTS in this same project (a reference clip with dynamic, energetic
delivery produces more expressive cloned output; a flat, calm reference produces flat output)?
No source found so far confirms or denies this for VoxCPM2 specifically - its architecture is
different (it has an explicit instruction channel Qwen3-TTS Base lacks), so the answer may not
carry over. Also unresolved: whether there's any practitioner-discovered technique - decoding
parameter combination, instruction-phrasing pattern, reference-clip curation practice, or
anything else - that goes beyond what's in the official docs for getting reliably in-character,
non-melodramatic, non-flat results.

Hard constraints on anything proposed: must preserve zero-shot cloning of an arbitrary supplied
reference clip; must not require fine-tuning per character (30+ speakers); must run on a single
consumer GPU (16GB VRAM class); Apache-2.0 license must be preserved (don't introduce a more
restrictive dependency without flagging it).

---

## The prompt itself

I'm using VoxCPM2 (`openbmb/VoxCPM2`) for zero-shot voice cloning of video game characters from
short reference clips of their real dialogue audio, combined with its "Controllable Voice
Cloning" feature (a free-text style/emotion instruction passed alongside the reference clip). I
already know the official documented basics (parameter ranges, the "don't stack too many
instructions" warning, the short-text instability limitation, and the known run-to-run variance)
- I'm not asking you to re-explain those. I'm looking for anything beyond the official docs:
real practitioner experience, workarounds, and specifically-tested findings. Please research and
report on:

1. **Reference-clip prosody transfer.** Does the reference clip's own delivery style/energy
   (calm and flat vs. dynamic and expressive) noticeably shape how expressive or flat the cloned
   output sounds, independent of the text instruction? Is this documented, discussed, or
   demonstrated anywhere (official docs, GitHub discussions, blog posts, video demos, forum
   threads)? If people have found that a more dynamic/varied reference clip produces better
   results even when using the instruction channel to also control delivery, that's exactly what
   I'm looking for - cite the actual source, don't infer from general TTS knowledge.

2. **Reported best practices for phrasing the `(...)` style instruction**, beyond "keep it
   simple." Are there example instructions practitioners have found reliably produce good,
   in-character results (not flat, not melodramatic)? Any reported difference between describing
   *emotion* (e.g. "angry", "sad") vs. describing *delivery mechanics* (e.g. "faster pace, lower
   pitch, clipped words") in terms of how reliably the model follows them without overacting?

3. **Any decoding-parameter combination beyond the documented defaults** that practitioners have
   found actually helps with voice-identity consistency or reduces melodramatic/flat delivery -
   specifically `cfg_value` and `inference_timesteps`, but also anything else exposed by the
   `VoxCPM.generate()` API (check the actual current API, don't assume it matches what I've
   described - it may have more parameters than what's officially documented). Real reported
   results with before/after comparisons are what I want, not speculation about what "should"
   work.

4. **Any workaround for the wrong-voice-entirely failure mode on short text**, beyond what's
   already documented (expect instability, retry). Has anyone found that padding short text with
   silence, prepending throwaway context text, adjusting the reference clip length/content, or
   anything else measurably helps? Or is this genuinely a dead end with the current model?

5. **Community sentiment and unresolved complaints.** Search GitHub issues/discussions on
   `OpenBMB/VoxCPM` beyond the three I already know about (#272 reference-echo, #191 wrong-gender
   voice switch, #302 long-form drift) for anything relevant to consistent in-character cloning.
   Also check Hugging Face discussions, Reddit, X/Twitter, Discord, and (since this is a Tsinghua/
   OpenBMB project) Chinese-language sources like Zhihu or Bilibili, which may have more detailed
   practitioner discussion than English-language channels.

6. **Whether a newer VoxCPM release or roadmap item addresses any of this** - check for anything
   more recent than what's in the current stable docs/release that specifically targets
   consistency, identity fidelity, or instruction-following reliability.

**Verification requirement:** for every concrete technical claim (a parameter value, a specific
GitHub issue/PR/discussion, a specific before/after result, a specific quote from OpenBMB staff
or a practitioner), cite the actual source and note whether you fetched/read it directly rather
than inferring it from a secondary summary or search snippet. This project has previously caught
research reports citing sources that turned out not to exist or not to say what was claimed -
treat every load-bearing technical claim as needing a real, checkable source, and say plainly
when something is speculation or your own reasoning rather than a reported finding.
