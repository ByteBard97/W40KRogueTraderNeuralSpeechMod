# Qwen3-TTS expressiveness: social media / informal practitioner findings

Companion to `qwen3-tts-emotive-expressiveness-research-prompt.md` — that prompt went to several
other research agents in parallel; this pass deliberately weighted X/Twitter, Chinese-language
sources, YouTube, and informal GitHub/HF discussion threads instead of official docs, since those
other agents already cover the official-docs/model-card angle thoroughly. Run 2026-09-16.

**Verification note:** every claim below was fetched directly (WebSearch + WebFetch) during this
session, not recalled from training data. Where I could not fetch a source directly (two X/Twitter
posts returned HTTP 402 from the fetch tool), I only report what the search-result snippet itself
showed verbatim, flagged as unverified-beyond-snippet, per this project's standing rule about not
presenting unconfirmed claims as solid citations.

## Headline finding: "flat/mechanical delivery" is a real, actively-discussed, unsolved complaint

This isn't a problem specific to this project's setup — it's the top community-reported gap for
Qwen3-TTS's Base (cloning) checkpoint. Direct evidence:

- **GitHub `QwenLM/Qwen3-TTS` Discussion #218** ("Emotion & Instruction Control for Voice
  Cloning"), opened by user **epigos**: a feature-request poll asking for emotion/prosody control
  on cloned voices, framed exactly as this project's problem — the model "accurately replicate[s]
  timbre and vocal characteristics but provide[s] limited control" over delivery. 17 votes split
  across three proposed mechanisms: inline emotion tags (52%), free-text instructions (47%), and
  low-level pitch/speed/energy parameters (0%). User **jdc4429** (Mar 21, 2026): *"It's so hard to
  get the right timing and emotion on a cloned voice."* No Qwen team response is visible in the
  thread, and no workaround is offered there — it's a live, unresolved feature request, not
  something already solved and just undocumented.
  https://github.com/QwenLM/Qwen3-TTS/discussions/218

- **HuggingFace `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` Discussion #38** and its GitHub mirror
  **Discussion #231** (same question, cross-posted): user **zaidbren** confirms directly what this
  project already found independently — passing an `instruction` to the **Base** model while
  cloning "produces no effect—it only clones the voice as-is."
  https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/discussions/38
  https://github.com/QwenLM/Qwen3-TTS/discussions/231

## The two workarounds people are actually reporting (both are fine-tuning, not prompt/decoding tricks)

No one found reported a *prompt-text* trick, decoding-parameter combo, or reference-clip-only
technique that adds real emotional range to Base without fine-tuning. Every concrete workaround
found is some form of fine-tuning:

1. **Community-reported informal recipe** (GitHub #231, user **notakwithac**, and separately
   **syyxsxx**): fine-tune the *CustomVoice* checkpoint (not Base) on samples of your target voice
   — clone the voice repeatedly, keep only the generations that stay close to the reference
   ("remove the voice samples that alter too much from the benchmark"), then fine-tune on that
   filtered set to get a checkpoint you can then instruct. syyxsxx reported back later in the same
   thread: *"I tried fine-tuning the Custom-Voice model. It works for a single speaker."*
   notakwithac separately called the general approach's results "mediocre at best," dependent on
   dataset size. Important caveat for this project: this fine-tunes **CustomVoice**, which starts
   from a fixed preset voice, not an arbitrary cloned reference — it's a per-character
   fine-tuning workflow (one adapter/checkpoint per voiced character), which is heavier than this
   project's stated preference (30+ speakers, no per-character training by default), but may still
   be worth it for a small number of lead characters like Abelard if the quality bar justifies it.

2. **A real, usable open-source LoRA fine-tuning toolkit exists**: `instavar/qwen3-tts-lora-
   finetuning` on GitHub, Apache-2.0 licensed (compatible with this project's constraints),
   packaging training scripts, inference utilities, and — notably — patches for **11 documented
   upstream bugs** in the official fine-tuning path, including a "double label-shift bug" that
   causes progressive speech acceleration during training, missing text-projection calls that
   crash training, a bad default learning rate that "produce[s] noise," sample-rate mismatches,
   and EOS-token failures — one of which is described as affecting "every run on the official
   script." Its documented production example is speaker-specific (a single Singaporean-English
   voice, "IMDA NSC FEMALE_01"), confirming this is per-voice fine-tuning, not a general
   expressiveness adapter. **It makes no claim of adding emotion/expressiveness** — it's about
   training correctness and stable per-voice adaptation, not solving the delivery problem itself.
   Still directly useful as a foundation if this project ever decides to fine-tune Abelard (or any
   lead character) specifically, since it's already fixed the upstream training bugs.
   https://github.com/instavar/qwen3-tts-lora-finetuning
   (companion write-up: https://instavar.com/blog/ai-production-stack/LoRA_Finetuning_Qwen3_TTS_Custom_Voices
   — not independently re-verified this session, found via search only)

3. **Commercial/managed option, X/Twitter, unverified beyond the search snippet** (fetch attempt
   returned HTTP 402, so this is reported only as what the search snippet itself showed, not a
   confirmed direct read): a post from **@baseten** states *"Qwen3-TTS supervised fine-tuning
   (SFT) for voice cloning is now available on Baseten Training. We see 16% faster time to first
   audio (TTFA) than other cloning techniques, with a high level of control over emotion and
   prosody."* This is a paid managed-training product, not a technique this project could run
   locally, and I could not verify the training-data requirements or license implications beyond
   this one sentence. Flagging for awareness only, not as something to act on without further
   direct verification.
   https://x.com/baseten/status/2083281029276569692 (unverified beyond snippet)

## Possible near-term fix from the Qwen team themselves — worth watching, not yet real

Two independent sources both point at the same upcoming release:

- GitHub Discussion #231, user **Shayano**: claims (citing unspecified "academic documentation")
  that combined instruction-following + cloning "will happen with the Qwen3‑TTS‑25Hz‑1.7B‑
  VoiceEditing model" and recommends waiting for its release.
- A WebSearch-synthesized summary of an official **@Alibaba_Qwen** X/Twitter post (search snippet
  only — the post itself returned HTTP 402 on direct fetch, so I could not read the full text or
  confirm this beyond the AI-generated search summary) stated: *"The Base model supports
  Instruct-style control for emotion and style, which is available in the upcoming open-source
  25Hz model release."*

These two independently point at the same model name/feature, which raises my confidence this is
a real, planned release rather than a hallucination on either side — but **neither source was
independently confirmed by me reading a primary page directly**, so treat "Qwen3-TTS-25Hz-1.7B-
VoiceEditing will support instruct+clone together" as a lead to check against the official GitHub
repo/HF org page directly (the other research agents' prompt already asks them to check for
recent releases — this is the specific model name to search for), not as a confirmed fact yet.

## Reference-clip prosody tip (corroborates, doesn't add beyond, what this project already found)

The `ocdevel.com` blog post (independent source, English-language, not social media but informal/
practitioner-written rather than official docs) states plainly: *"Including varied intonation in
the reference clip is recommended. The reference teaches the model not just what your voice
sounds like, but how you speak — pitch range, rhythm, breathing patterns"* and warns *"a monotone
source will produce monotone outputs."* This matches this project's own empirical finding
(cloning quality/delivery tracks the reference clip's own performance) but adds no new mechanism
beyond what's already been tried. The same post also independently corroborates this project's
separate finding that Qwen3-TTS's accent fidelity is fragile/unreliable for non-American English
reference voices — consistent with, not new information beyond, prior verified findings in this
project.

## Chinese-language sources (Zhihu, Bilibili): no distinct technical content found

Searched Zhihu and Bilibili directly (search-engine level, not deep individual post fetches, given
fork scope/time budget). Results were overwhelmingly marketing/tutorial content — "how to install
Qwen3-TTS locally," feature announcements, ComfyUI integration guides — restating the same official
capability claims (3-second cloning, low VRAM, natural-language emotion control *on CustomVoice/
VoiceDesign*, not Base+clone) rather than practitioner complaints or workarounds specific to the
Base+clone expressiveness gap this project cares about. This may reflect a real gap (Chinese
content is skewing toward "how to use the tool" rather than "here's what's broken and how I fixed
it"), or may reflect the shallow depth this search pass could reach (top-level web search rather
than reading full Zhihu answer threads or Bilibili video comment sections one by one). If this
gap matters enough to the decision, a deeper pass reading actual Bilibili video comment sections
(not just video titles/descriptions) would be the next step — not done here due to scope.

## Bottom line for this project

- No shortcut exists. Every real, concrete answer found is a form of fine-tuning, none of them
  are a free prompt/decoding trick.
- The most promising near-term path if this project wants to chase Base+expressiveness now:
  the `instavar/qwen3-tts-lora-finetuning` repo — real, Apache-2.0, already fixes 11 documented
  upstream training bugs — but it's a per-voice fine-tune, meaning realistically only worth it for
  a small number of lead characters (Abelard being the obvious first candidate given how far this
  bake-off has gone), not all 30+ speakers.
- The most promising near-term path if this project can wait: check whether **Qwen3-TTS-25Hz-
  1.7B-VoiceEditing** has been released or has a firm release date — two independent but each
  individually unconfirmed sources both suggest it may solve this natively. Worth a direct,
  primary-source check (official GitHub repo releases page / HF org page) rather than trusting
  either source found here on its own.
