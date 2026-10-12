# Automated scoring of cloned TTS output (speaker similarity + emotion) — research agent prompt

One self-contained prompt below. Copy the whole section into a research agent (Gemini, Claude,
Kimi deep-research or similar). It repeats project context so it stands alone.

## Prompt

### Context

I'm building a fan-made TTS mod for a story-heavy RPG (Warhammer 40,000: Rogue Trader). About 90%
of the game's dialogue ships unvoiced. I'm voicing it by zero-shot cloning each character from short
reference clips (roughly 5-30 s) taken from that character's real voiced lines in the game. I have
two finalist TTS engines: VoxCPM2 (`openbmb/VoxCPM2`, 2B params, 48 kHz, supports a free-text
style instruction plus a reference wav) and Qwen3-TTS Base (cloning only, no instruction channel).

My current workflow is a person listening to every generated clip and rating it 1-5 on two axes.
That doesn't scale. For one character I have about 447 target lines, roughly 136 candidate
reference clips grouped by emotion, and several knobs (reference clip choice, cfg_value 1.5-5.0,
inference timesteps, instruction text, engine, retakes). Run-to-run variance is high and there is
no seed control, so I need many samples per setting. I have already spent hours rating a 228-clip
sweep by hand and I don't want to do that again.

**The goal is an automated loop:** generate clips, score them with a model instead of my ears, and
use the scores to pick the best reference clip and settings per line or per emotion (grid search,
Bayesian optimisation, or best-of-N retakes). A human should only spot-check the winners.

### What the scorer must measure

1. **Voice match.** Does the generated clip sound like the same person as the reference clip? This
   is timbre and identity, not delivery. It must catch the failures I actually see: wrong voice
   entirely (especially on short lines), gravelly or whispery artifacts, wrong pitch range,
   rhotic-R accent drift, and the tail of the reference audio leaking into the output.
2. **Emotion rendered.** Does the performance convey the intended emotion (for example stern,
   anxious, sardonic, grieving, angry, warm), and at a believable intensity? Emotion labels are
   free-form, about 56 distinct ones, and I also have PAD (pleasure/arousal/dominance) coordinates
   for the reference clips. The character's baseline is stern and formal, so "flat" and
   "melodramatic" both count as failures.
3. **Naturalness / artifacts** (secondary). Robotic or garbled speech, clipping, dropped or
   repeated words, mispronunciations, wrong speed, long silences.

### Content (game audio and text)

The speech is English, stylised fantasy-sci-fi, some heavily accented or unusual delivery. Text
often contains invented proper nouns and Gothic-style names. The reference audio is game-rip
quality: 44.1/48 kHz but with music-bed or reverb in some clips. My ground truth is small: about 228
human ratings (1-5 voice, 1-5 emotion) plus failure tags (gravelly, whisper, too high, rhotic R,
rushed) on cloned output, and 136 reference clips with human-verified emotion labels.

### Hardware and constraints

- One consumer GPU, RTX 5080 with 16 GB VRAM, shared with the TTS engines (VoxCPM2 alone takes
  about 7.7 GB, Qwen3-TTS about 2.4 GB). The scorer should fit in roughly 4-6 GB or run on CPU
  or a remote API.
- Linux, Python. The TTS engines live in separate conda/venv environments, so the scorer will
  likely run as its own process.
- Must be cheap per clip. I want to score thousands of clips.
- Open source, self-hosted models are preferred. Paid APIs and commercial products are also in
  scope for comparison, but I want prices.
- Licence matters: this is a non-commercial fan mod, but say which options are non-commercial-only.

### What I need from you

Research and report on **all** of the following. Verify claims against primary sources (model
cards, papers, official docs, real GitHub issues). Cite a URL for every load-bearing claim. If you
can't fetch a source, say so instead of citing from memory. Do not invent model names, benchmark
numbers, or API endpoints. Mark anything you couldn't verify.

**A. Speaker-similarity scoring (voice match).**
- The standard approach is speaker-embedding cosine similarity (SIM-o in the zero-shot TTS
  literature). Compare the real options: WavLM-TDNN / WavLM-large-SV, ECAPA-TDNN (SpeechBrain),
  TitaNet, Resemblyzer, pyannote embedding, CAM++, ERes2Net, and any newer ones (2025-2026).
  For each: repo/HF link, licence, VRAM, speed, and known weaknesses.
- Key question: how well do these embeddings hold up on **short clips (1-3 s)**, on **stylised or
  emotional speech**, and when the two clips differ in **emotion** (speaker embeddings are known to
  shift with emotion)? What is a sensible similarity threshold, and is there published guidance on
  calibrating it per speaker?
- How do TTS papers (F5-TTS, CosyVoice, MaskGCT, Seed-TTS-eval, VoxCPM, Qwen3-TTS) measure
  speaker similarity, and which checkpoint do they use?

**B. Emotion scoring (speech emotion recognition).**
- Open models: emotion2vec / emotion2vec+ (FunASR), wav2vec2/HuBERT/WavLM emotion heads (for
  example audeering's dimensional wav2vec2 model that outputs arousal/valence/dominance), SpeechBrain
  IEMOCAP models, Whisper-based SER, Qwen2-Audio and other audio-LLMs used as emotion judges, and
  anything newer. For each: label set (categorical versus dimensional), training data, licence,
  VRAM, and known accuracy on acted or stylised speech versus real speech.
- Important: my labels are 56 free-form emotions and PAD coordinates, not the usual 4-9 basic
  emotions. Can a **dimensional (arousal/valence/dominance) model** be used to compute distance
  between the generated clip and the target emotion? Can I instead compare emotion embeddings of
  the generated clip against the emotion embedding of a reference clip that is known to have the
  target emotion (embedding-space similarity, so no label mapping is needed)?
- Are there models that score emotion **intensity/appropriateness relative to the text** or that
  evaluate "emotional expressiveness" of TTS specifically (EmoBench-style, EmoSphere, emotion
  similarity metrics from TTS papers, Emo-SIM, etc.)?
- Known failure modes: acted-speech bias, English-only, language or accent sensitivity, poor
  behaviour on non-neutral baselines (a stern character reads as "angry" to a naive classifier).

**C. Audio-LLM and MOS-predictor judges.**
- Audio-language models that can take a wav and a rubric and return a structured score: Qwen2.5-Omni,
  Qwen2-Audio, Kimi-Audio, Step-Audio, Gemini (audio input), GPT-4o audio, others. How reliable
  are they as TTS judges? Look for published studies of LLM-as-judge on speech quality or emotion,
  their agreement with human ratings, position/length bias, and cost per clip.
- Naturalness / MOS predictors: UTMOS / UTMOSv2, DNSMOS, NISQA, SQUIM, Audiobox-Aesthetics, MOSNet
  and newer ones. Licence, VRAM, and whether they detect gravelly, whispery or robotic
  artifacts.
- Anything that scores **pairwise** ("which of these two clips is closer to the reference in
  emotion") rather than absolute.

**D. Existing end-to-end TTS evaluation toolkits.**
- Toolkits that bundle several of these metrics: `seed-tts-eval`, `VERSA`, `TTS-eval` suites,
  `Emilia`/`Amphion` evaluation tools, `SpeechBrain` recipes, `torchaudio.pipelines` (SQUIM), `ESPnet`
  evaluation, `Meta audiobox-aesthetics`, `Cotrain/Talk Arena`-style benchmarks. Which ones are
  installable and actively maintained, and which are research code that no longer runs?
- ASR-based checks for dropped, repeated or hallucinated words (Whisper WER against the input
  text): are there recommended settings, and how does WER hold up on invented fantasy names?

**E. Commercial and hosted options.**
- Hosted services that score voice similarity, emotion or overall TTS quality (for example
  ElevenLabs, Resemble AI, Hume AI's expression measurement, Azure/Google/AWS speech analytics,
  Speechmatics, AssemblyAI, Deepgram, Picovoice, Play.ht, and any voice-verification or
  deepfake-detection APIs used as similarity scorers). Note pricing per audio minute or per call,
  rate limits, accuracy claims, and terms restrictions (for example bans on using their output to
  train competitors).
- For Gemini/GPT-class audio input specifically: cost per 1k clips of ~5 s, and any published
  evidence on emotion-rating quality.

**F. Validating the scorer against my human ratings.**
- How should I check that an automated score tracks human judgement with only ~228 rated clips?
  Recommend a concrete procedure (Spearman/Kendall correlation per axis, per-line ranking
  agreement, top-1 agreement in best-of-N selection, and how to handle rater noise). What
  correlation is "good enough" to trust the scorer for search?
- How to combine metrics into one objective (weighted sum, hard gates like "voice sim must exceed
  X, then maximise emotion", Pareto front) without Goodhart-style gaming (for example the scorer
  rewards over-acted shouting).
- Reward-hacking and bias risks: the emotion model preferring loud output, the similarity model
  preferring the reference's own reverb or recording channel, and length effects.

**G. The optimisation loop.**
- What is the state of the art in **automated best-of-N selection and parameter search for TTS**?
  Look for papers or projects that do automatic reranking of TTS samples, "TTS with rejection
  sampling", DPO/GRPO with speaker-similarity and emotion rewards (for example Seed-TTS RL,
  F5R-TTS, DiffRhythm-style rewards, and Qwen3-TTS or VoxCPM fine-tune recipes), and lightweight
  black-box optimisers (Optuna/TPE, successive halving) applied to inference-time knobs.
- Practical design: how many samples per (line, setting) are needed to overcome run-to-run
  variance when the scorer itself is noisy? Suggest a budget-aware search design for about 447
  lines x ~7 anchor references x a few cfg values.
- Reference-clip selection: any published method for choosing the **best reference clip** for
  zero-shot cloning (for example scoring candidates by downstream similarity, clip quality,
  duration, and emotional match)?

### Output format

1. A **short recommendation up front**: the specific stack I should try first for (a) voice
   similarity, (b) emotion, (c) artifacts/naturalness, and (d) an audio-LLM judge, with a
   fallback for each. Say why.
2. A **comparison table per section (A-E)**: name, link, licence, VRAM/speed, what it measures,
   known weaknesses, and confidence (verified from primary source / secondary / unverified).
3. A **minimal working pipeline sketch**: the Python-level steps from "generate clip" to
   "combined score", including which pip packages or HF model IDs to use. Code snippets are fine
   if you verified the API against the docs.
4. A **validation plan** (section F) I can execute with my 228 rated clips.
5. **What you could not find or verify**, and any claims you found that conflict between sources.
6. A list of **dead ends**: popular-sounding tools that don't do what they claim, are abandoned,
   or have licences that rule them out.

Plain prose in the report, no hype. If the honest answer is "automatic emotion scoring of acted
game dialogue is not reliable yet, use X only as a coarse filter", say so and say what the coarse
filter can and cannot catch.
