# Mac mini audio-LLM plan (for when the Mac is free)

Goal: find out whether a large local audio-LLM (Mac mini M5 Pro, 64 GB unified memory) can act
as a second emotion judge for the automated TTS scoring loop, where the 5080-sized options
failed. Everything below is testable with data we already have; no new hand-rating is needed.

## Why this is worth doing

Emotion is the one axis the free metrics do poorly on. State as of 2026-09-24 (all on the 136
ear-labelled Abelard clips, 8 families, majority baseline 23.5%):

| Method | Top-1 |
|---|---|
| Qwen2-Audio-7B (pilot 1, free-form) | 3.8%, 67% parse failures |
| Qwen2.5-Omni-7B 4-bit, forced choice, audio only | 36.8% (says "stern" for 104/136 clips) |
| same, with transcript | 41.2% |
| audEERING embedding + logistic probe, leave-one-out | 43-46% |

The 7B model mostly answers "stern" (Abelard's baseline). A larger model may separate delivery
better. Pairwise judging by the 7B was position-biased (answered "A" on 92% of triples).

**Update 2026-09-25:** the MLX conversion of Qwen3-Omni-30B-A3B reports text-only inference (audio needs a hacky PyTorch+MLX hybrid),
so `mlx-vlm` audio may fail at the smoke test. See `open-source-emotion-judges-survey.md` for fallbacks (PyTorch on MPS with
Qwen2-Audio / Qwen2.5-Omni, LoRA tuning, and EmpathicInsight-Voice).

## Candidates (from the research pass; runtime support on Mac still to be confirmed by running)

1. **Qwen3-Omni-30B-A3B-Instruct** via `mlx-vlm` (`pip install -U mlx-vlm`).
   Repos seen in the HF listing: `mlx-community/Qwen3-Omni-30B-A3B-Instruct-{4,5,6,8}bit`, plus
   `ZolMik2004/Qwen3-Omni-30B-A3B-Instruct-HybridQuant-MLX` (22.55 GB, card says 32 GB unified
   memory is enough). bf16 is 70.5 GB, too big. Apache-2.0. Known issue: mlx-vlm #2099 (audio+video
   together crashes; audio only reported working). Try 8-bit first, fall back to the hybrid quant.
2. **Gemma 4 E4B / 12B** via `mlx-vlm` (`mlx-community/gemma-4-e4b-it-4bit`) or llama.cpp
   (`ggml-org/gemma-4-E4B-it-GGUF`). Audio is capped at 30 s. Needs an mlx-vlm that includes
   PR #931 (earlier versions gave gibberish on audio).
3. **llama.cpp GGUF of Qwen3-Omni / Qwen2.5-Omni-7B** mainly for grammar-constrained output.
   llama.cpp calls audio "highly experimental".

## Experiments, in order (stop as soon as one clearly fails)

Every experiment reuses code and data already in the repo:
- Single-clip family labels: `tools/audio_emotion_labeling/omni_pilot.py`, `families.py`,
  `score_pilot2.py` and the 136-clip ground truth in `data/voices/emotion_banks/curation.json`.
- Pairwise judging: the human-answered A/B pairs in `data/scorer_probe/best_of_n/pairs.json` and
  `answers.json` (voice and emotion axes). This is a real benchmark of "does the judge agree with the
  user's ears on generated speech", which the 136 real clips cannot measure.

1. **Smoke test.** Load the model, feed one 5 s clip, get a sane answer. Confirm audio input works
   (not gibberish), record seconds per clip and peak memory. Then confirm one request can carry
   three audio inputs (reference, A, B). If either fails, drop the model.
2. **Family classification, 136 clips.** Same forced-choice prompt and strict JSON as the 7B pilot.
   Constrained first-token decoding if the runtime supports it (else parse and retry once).
   Subtract the per-family prior (mean logit over the whole set) before argmax, since the 7B
   collapsed to one class. Report top-1, macro-recall, per-family recall, parse failures.
   **Pass:** clearly above the embedding probe's 46% and the 7B's 41%, with recall > 0.3 on at least
   6 of 8 families. Otherwise the LLM adds nothing over the free probe and we stop.
3. **Pairwise, human-answered pairs.** For each pair run both orders (A,B) and (B,A) and count a
   verdict only when both orders agree. Report agreement with the user's answers per axis, the
   position-bias rate (how often the answer follows the slot, not the clip), and the fraction of
   pairs with consistent verdicts. **Pass:** agreement with the user's decisive answers above 75%
   on the emotion axis with a majority of pairs consistent; compare against the scorer's own
   agreement (see `analyze_answers.py`).
4. **If 2 or 3 passes:** decide the role. Best use is a second opinion on lines where the free
   scorer flags `low_emotion_prob` or the top two takes are close, not a primary ranker. Write the
   service as a small HTTP endpoint on the Mac so `bon_score.py` on the Linux box can call it.
   Batch overnight; the Mac is only needed for the shortlist, not every take.

## What to record

Model id, quantization, runtime + version, seconds per clip, peak memory, prompt text, and the
metrics above, appended to `data/audio_llm_pilot2/report.md` (or a `mac_` prefixed sibling).

## Setup on the Mac

**Ready-made:** `python3 tools/mac_pilot/build_bundle.py` writes `data/mac_pilot_bundle/` (about 200 MB: 136 real clips,
31 A/B pairs, runner, README). Copy that folder to the Mac and follow its README; the runner is stdlib-only and talks to an
OpenAI-compatible audio server (`mlx_vlm.server` or `llama-server`). Verified only against a stub server; whether the
real servers accept audio is what its `smoke` step checks. Steps 1-3 below are implemented by `run_pilot.py`.

Manual notes:

- Copy the repo's clips and JSONs needed: `data/voices/wav/Abelard/`, `curation.json`,
  `data/scorer_probe/best_of_n/` (wavs, `pairs.json`, `answers.json`) and the pilot scripts.
  Nothing needs the CUDA environment.
- Create a fresh venv on the Mac; do not reuse the Linux ones.
- Use a job that writes results to disk after every clip so a reboot or a busy Mac loses nothing.
