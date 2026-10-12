# Qwen3-TTS: getting emotive/naturalistic delivery without losing the cloned voice — research agent prompt

One self-contained prompt below — copy the whole section into a research agent (Gemini/Claude/
Kimi deep-research or similar). It repeats project context so it stands alone.

## Shared background (for you, not required reading for the agent)

Fan-made TTS mod for a story-heavy RPG (Warhammer 40,000: Rogue Trader). Character voices are
zero-shot cloned from short reference clips (~2-40s) of that character's real in-game dialogue
audio. Qwen3-TTS (`Qwen/Qwen3-TTS-12Hz-1.7B-Base`, Apache 2.0) is one of the strongest-performing
engines in an internal bake-off so far — frequently ranked #1 or #2 by blind listener preference
against 4 other engines — but its delivery reads as flat/mechanical: correct words, correct
cloned voice identity, no real emotional performance.

Prior research already done in this project (cited so the agent doesn't re-derive it from
scratch, checked directly against primary sources — official model cards and a koboldcpp
maintainer-adjacent discussion):

- **No released Qwen3-TTS checkpoint combines zero-shot voice cloning with instruction-following
  in one call.** `Qwen3-TTS-12Hz-1.7B-Base` clones a supplied reference clip but silently ignores
  any `instruct`/style-description text passed alongside it — confirmed empirically in this
  project (an `instruct` kwarg reaches the code path but the underlying library call has no
  parameter for it). `CustomVoice` and `VoiceDesign` checkpoints *do* follow free-text
  instructions, but only against 9 fixed preset voices — they cannot take an arbitrary reference
  clip at all. This is treated as settled/verified, not something to re-litigate from scratch.
- Separately (this project's own debugging, not published research, but worth the agent knowing
  as context): Base's zero-shot cloning also breaks in an unrelated way when the reference clip's
  transcript text doesn't match what's actually spoken in the reference audio (e.g. game-script
  narration text mixed in with quoted dialogue, when only the dialogue was voiced) — causes the
  model to never predict a stop token. Not what this prompt is about; mentioned only so the agent
  doesn't waste time on it if it surfaces the same issue under a different name.

**What's genuinely unresolved, and the actual point of this prompt:** is there any way, using
only the `Base` checkpoint (since it's the only one that clones an arbitrary reference voice), to
get more expressive/emotionally varied delivery than the flat default — without a
formally-supported instruction API? Given the underlying architecture is an autoregressive
LLM-plus-audio-codec model (not a classic TTS pipeline), there's a real chance behavior can be
steered the way base LLMs are sometimes steered into unsupported behaviors via prompt
construction, decoding parameters, or clever use of the reference clip itself, even without an
official feature for it.

Hard constraints on anything proposed: must preserve zero-shot cloning of an arbitrary supplied
reference clip (not a preset voice); must not require full fine-tuning per character (30+
speakers, no plan to train per-character models by default, though a single shared LoRA/adapter
across all characters would be acceptable if it doesn't need per-character training data beyond
what's already used for cloning); ideally runs on a single consumer GPU (16GB VRAM class);
license must stay compatible with a free public mod (Apache-2.0/MIT class - Qwen3-TTS itself is
Apache-2.0, so anything proposed shouldn't reintroduce a more restrictive dependency without
flagging it clearly).

---

## The prompt itself

I'm using Qwen3-TTS's `Base` checkpoint (`Qwen/Qwen3-TTS-12Hz-1.7B-Base`, via the official
`qwen-tts` PyPI package / `qwen_tts.Qwen3TTSModel.generate_voice_clone`) for zero-shot voice
cloning from short reference clips of a video game character's real dialogue audio. Cloned voice
identity is good, but delivery is flat and mechanical — it doesn't perform emotion (anger,
dread, wry humor, grief, etc.) even when the target text clearly calls for it. I know the `Base`
checkpoint has no supported instruction-following API (confirmed against the official model
card), so I'm not asking whether Qwen3-TTS supports an `instruct` parameter on Base — it doesn't.
I'm asking whether people have found *other* ways to get more expressive output out of it while
still cloning an arbitrary reference voice. Specifically:

1. **Has this changed?** Has Alibaba/Qwen released any newer Qwen3-TTS checkpoint, update, or
   documentation (since early September 2026) that adds instruction-following to a
   cloning-capable checkpoint, or otherwise changes this tradeoff? Check the official
   `QwenLM/Qwen3-TTS` GitHub repo and Hugging Face model cards directly, not just secondary
   sources, and give exact dates/version numbers for anything found.

2. **Reference-clip selection as an indirect expressiveness lever.** Since Base has no
   instruction API, the reference clip's own prosody is presumably the only thing currently
   shaping delivery style. Is this documented/reported anywhere for Qwen3-TTS specifically (or
   for similar ICL-based zero-shot codec-LM TTS architectures generally, e.g. other systems using
   the same class of "in-context learning from a reference audio+text pair" cloning)? Is there a
   reported best practice for picking or constructing a reference clip so that its *delivery
   style* (not just speaker identity) carries over into generated output — e.g. does the model
   tend to imitate the reference clip's specific emotional register on a given generation, and if
   so has anyone characterized how strongly, or how to select/curate reference clips to lean into
   this? Genuine citations only (GitHub issues/discussions, HF discussions, papers, technical
   blog posts, Reddit/Discord threads from people who've actually tried this) — don't speculate
   from general TTS knowledge if you can't find a source specific to this class of model.

3. **Prompt/text-side tricks on the Base checkpoint.** Since the underlying architecture is an
   autoregressive LLM generating audio codec tokens (not a classical acoustic-model TTS
   pipeline), has anyone reported success influencing delivery through the *text itself* rather
   than a formal instruction parameter — e.g. embedding stage directions, tone words, punctuation/
   capitalization tricks, or descriptive framing directly in the text passed to `generate_voice_
   clone`, the way some users coax base (non-instruct) LLMs into following patterns they weren't
   explicitly trained for? Has anyone published concrete before/after examples, or is this purely
   speculative? Also check whether any of this bleeds into mispronunciation/gibberish (a known
   failure mode when this class of model gets an unexpected text distribution) so I know the risk
   side, not just the upside.

4. **Decoding-parameter tuning for expressiveness.** `generate_voice_clone` exposes `temperature`,
   `top_k`, `top_p`, and `repetition_penalty`. Has anyone documented a temperature/top_p/
   repetition_penalty combination that meaningfully increases perceived expressiveness/dynamic
   range on Qwen3-TTS specifically (not generic LLM sampling advice) — and what's the reported
   cost (garbling, mispronunciation, instability, losing the cloned identity)? I already know
   `do_sample=True` at defaults (`temperature=0.9, top_k=50, top_p=1.0, repetition_penalty=1.05`)
   produces flat delivery; I'm looking for anyone who's actually pushed these and reported what
   happened, not general "raise the temperature" guessing.

5. **Fine-tuning / LoRA approaches.** Has anyone published a fine-tuning or LoRA recipe for
   Qwen3-TTS that adds expressive/emotional range on top of (not instead of) zero-shot cloning —
   ideally something that doesn't require per-character training data beyond what's already used
   for cloning (e.g. a general "add expressiveness" adapter trained on a separate emotional-speech
   dataset, applied on top of any cloned voice, rather than one adapter per character)? If real
   examples exist, what dataset(s) did they train on, how much compute/data did it take, and what
   license is the resulting adapter/recipe under? Flag clearly if this is genuinely unexplored
   territory rather than forcing an answer.

6. **Community consensus check.** Broadly: among people actually using Qwen3-TTS Base for
   cloning (not CustomVoice/VoiceDesign), is "flat/mechanical delivery" a commonly reported
   complaint, and if so is there any converging community opinion on the best available
   workaround today, however partial? Or is the honest answer that this is currently an
   unsolved/accepted limitation of the checkpoint?

**Verification requirement:** for every concrete technical claim (a parameter value, a specific
GitHub issue/PR, a specific fine-tuning result, a specific quote from Qwen/Alibaba staff), cite
the actual source and, where feasible, note that you fetched/read it directly rather than
inferring it from a secondary summary. This project has previously caught a research report
citing a GitHub repo that didn't exist to support its top recommendation — treat any load-bearing
technical claim as needing a real, checkable source, and say plainly when something is
speculation/your own reasoning rather than a reported finding.
