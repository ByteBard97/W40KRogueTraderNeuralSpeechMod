# VoxCPM2: getting consistent, in-character results — research findings

Research pass on getting VoxCPM2 (openbmb/VoxCPM2, Apache-2.0) to clone a fixed character's voice
consistently and stay in-character across delivery instructions, decoding parameters, and
short-text edge cases. Run 2026-09-16. Every claim below was fetched directly (WebSearch +
WebFetch) this session; nothing is recalled from training data. No fabricated-source problems
were found this pass — unlike the earlier Qwen3-TTS "task-vector" incident in this project, every
load-bearing claim here traces to a real, fetched page (official docs or a real, open GitHub
issue), cited below.

## 1. Confirmed: short target texts are a documented instability, not just this project's bad luck

The official Usage Guide states directly: *"Very short inputs like 'Hello' or '好的' may sound
weak. The model was trained with a minimum audio length of around one second, so inputs naturally
producing several seconds of speech prove more stable."*
https://voxcpm.readthedocs.io/en/latest/usage_guide.html

This independently corroborates this project's own empirical finding (three separate short lines,
all under ~40 characters, all producing wrong-voice output) — it's a real, acknowledged model
limitation, not a fluke. **No official workaround beyond "expect instability on short text"** is
offered; there's no minimum-padding trick or parameter documented to fix it. Practical
implication: treat any target line under roughly 40-50 characters as needing extra scrutiny (more
retakes, or default to qwen3_tts for those specific lines) rather than trying to engineer around
it.

## 2. Confirmed: stacking emotional descriptors in the instruction is a documented anti-pattern

The official cookbook states plainly: *"Adding too many complex voice instructions might spoil
the broth,"* recommending concise single-focus style modifiers (its own example: "speaking very
fast, bright and full") over stacked descriptors.
https://voxcpm.readthedocs.io/en/latest/cookbook.html

This directly supports the theory already being tested in this project: the fear-line instruction
("Deliver as a shaken, whispered prayer, genuine dread breaking through his composure at the
horrifying sight") stacks four distinct descriptors (shaken / whispered / genuine dread /
horrifying) in one instruction — exactly the pattern the model's own documentation warns against.
The toned-down rewrite being tested ("quiet, restrained unease... composure mostly intact") is
already aligned with the *right* direction per this guidance: fewer, more restrained descriptors,
not zero emotional content.

## 3. Confirmed: cfg_value and inference_timesteps guidance (this project has never tuned these)

From the official API reference and usage guide:
https://voxcpm.readthedocs.io/en/latest/reference/api.html
https://voxcpm.readthedocs.io/en/latest/usage_guide.html

- **`cfg_value`** (classifier-free guidance scale): default 2.0, documented range 1.0–3.0.
  - 1.0–2.0: more natural, but may drift further from the target text/instruction.
  - 2.0: balanced default (what this project currently uses, unexamined).
  - 2.0–3.0: stricter adherence to conditioning, at risk of noise/artifacts on difficult inputs.
- **`inference_timesteps`** (diffusion steps): default 10, documented range 4–30, roughly linear
  cost scaling (doubling timesteps ~doubles generation time), diminishing quality returns past
  ~30.

Nothing in official docs claims raising `cfg_value` fixes voice-identity drift specifically, but
the *mechanism* (stricter adherence to conditioning, which includes the reference-derived speaker
embedding) is directly relevant to the "wrong voice entirely" failure mode. This project has never
tested above the accepted 2.0 default — a controlled test at `cfg_value=2.5` on a known-bad short
line, and separately at `inference_timesteps=20`, would be a cheap, concrete experiment neither
this research pass nor this project's own testing has actually run yet. Treat this as an
unconfirmed lead worth testing empirically, not a proven fix.

## 4. Confirmed: reference-clip guidance (length, cleanliness) — no prosody-transfer finding either way

Official guidance, consistent across two pages:
https://voxcpm.readthedocs.io/en/latest/usage_guide.html
https://voxcpm.readthedocs.io/en/latest/cookbook.html

- 5–30 seconds is the documented practical range (cookbook: *"at least 5 seconds... the more
  high-quality audio you provide, the better the clone"*).
- Cleaner reference audio yields better timbre preservation; a `denoise=True` parameter exists
  for noisy source material (not currently used by this project's adapter), with the caveat that
  denoising may slightly alter voice characteristics.
- Explicit limitation, stated directly: *"You cannot perform arbitrary identity transformations
  from cloning alone"* — cloning shapes delivery (emotion, pace, volume) on top of a fixed
  timbre/identity, it does not let instruction text override the reference's core identity.

**No source found (official or third-party) explicitly confirms or denies whether the reference
clip's own prosody/dynamic range transfers into output the way this project found for Qwen3-TTS.**
This is a real gap — VoxCPM2's architecture is different (has its own explicit instruction
channel, unlike Qwen3-TTS Base), so the Qwen3-TTS finding may not carry over cleanly, and nothing
found here confirms it does. Flag as untested for VoxCPM2 specifically.

## 5. Real, verified bugs matching this project's own failure modes — from the actual issue tracker

Three open GitHub issues on `OpenBMB/VoxCPM` directly corroborate patterns this project already
hit independently:

- **Issue #272 — "VoxCPM2 Chirp/Click Artifact & Voice Consistency in One-Shot Cloning."** Reports
  a chirp/click artifact where the *tail of the reference audio leaks into the start of generated
  output* (their example: reference ending in "enemy" causes output to start with "emy") — the
  reporter traces this to the DiT's `prefix_feat_cond` conditioning. This is the same class of bug
  as Qwen3-TTS's independently-confirmed issue #341 (reference-tail echo) found in this project's
  earlier Qwen3-TTS research — a pattern across this whole family of ICL-conditioned voice-cloning
  architectures, not unique to either model. The reporter tried six mitigations (padding, latent-
  only conditioning, zero-conditioning patches, dual conditioning, PCM trimming, transcript
  verification) — only PCM trimming ("removing approximately 2 audio patches") partially helped;
  none fully resolved it, and no maintainer response is recorded.
  https://github.com/OpenBMB/VoxCPM/issues/272

- **Issue #191 — "Background noise and model suddenly switched voice to another gender."** Thin on
  detail (closed, no comments captured), but directly confirms "wrong voice entirely" (not just
  wrong delivery) is a real, independently-reported VoxCPM2 failure mode — corroborating this
  project's short-line "wrong voice" pattern, though this specific report doesn't establish text
  length as the trigger.
  https://github.com/OpenBMB/VoxCPM/issues/191

- **Issue #302 — "Long-form voice cloning drift."** A different failure mode than this project has
  hit (long generations drifting away from the reference over time, as the decoder's conditioning
  becomes progressively dominated by its own prior output rather than the original reference
  anchor: `prefix_feat_cond = pred_feat` at each step). Not directly relevant to short-line
  failures, but relevant if this project ever generates long single-call lines — current
  workaround reported is splitting long text into segments and re-anchoring reference audio per
  segment. A proposed "voice anchor" mechanism (`voice_anchor_strength`, `voice_anchor_tail_size`)
  is discussed but not implemented; issue is open, no maintainer response recorded.
  https://github.com/OpenBMB/VoxCPM/issues/302

## 6. Run-to-run variance: no smarter mitigation found than "generate and pick the best"

Confirmed again (matching what this project already knew): *"Voice Design and Controllable Voice
Cloning results can vary between runs... generate 1~3 times to obtain the desired voice or
style,"* with OpenBMB "actively working on improving controllability consistency" (unspecified
timeline). The cookbook adds color on why: *"every generation can still have subtle, unique
variations, a bit like hiring a new voice actor each time."* No parameter, seed-control technique,
or automated "pick the best take" heuristic was found anywhere (official docs, issues, or
practitioner discussion) beyond blind manual retries. This is a genuinely accepted, unsolved
limitation — not a gap in this project's own research.

## Bottom line for this project

- **Confirmed, actionable now:** the fear-line instruction problem is a known anti-pattern
  (stacked descriptors) with official guidance pointing at the fix already being tested (fewer,
  more restrained descriptors). Apply this as a general rule for all future VoxCPM2 instruct text,
  not just this one line.
- **Confirmed, not fixable:** short target texts (roughly under 40-50 characters) are a real,
  acknowledged model limitation with no documented workaround — budget for extra retakes or route
  very short lines to qwen3_tts instead.
- **Unconfirmed, worth a cheap test:** raising `cfg_value` toward 2.5 (still within documented
  range) on a known-bad short line, to see if stricter conditioning adherence reduces "wrong
  voice" drift — no source confirms this works, but the mechanism is plausible and untested.
- **Real, relevant upstream bug:** issue #272's reference-tail leak is the same bug class as
  Qwen3-TTS's #341 — if this project ever hears a short chirp/leak at the very start of a VoxCPM2
  clip, this is why, and there's currently no full fix upstream.
- **Genuinely unknown:** whether reference-clip prosody dynamism transfers into VoxCPM2 output the
  way it does for Qwen3-TTS. No source confirms or denies this — would need this project's own
  controlled test to establish.
