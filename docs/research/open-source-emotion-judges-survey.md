# Open-source emotion judges for generated TTS (survey, 2026-09-25)

Question: what free models could judge whether a generated clip delivers the intended emotion, given that
emotion2vec similarity failed here and the 7B audio-LLM pilot collapsed to "stern"? Sources are the papers and
model cards linked below; anything not read in full is marked unverified. Nothing here has been run yet.

## Findings that change the plan

1. **Qwen3-Omni on the Mac may not accept audio through MLX.** The `pherber3/Qwen3-Omni-30B-A3B-Instruct-4bit-mlx`
   card says "supports text-only inference"; audio needs a hybrid hack (PyTorch audio tower feeding MLX embeddings).
   `docs/research/mac-audio-llm-plan.md` assumed `mlx-vlm` audio works; that is unconfirmed and this is evidence
   against it. The bundle's `smoke` step will settle it, but plan a fallback: run Qwen2.5-Omni-7B or Qwen2-Audio-7B in
   bf16 through PyTorch on the MPS backend (about 15 GB, fits 64 GB), or use a non-LLM judge (item 2).
2. **EmpathicInsight-Voice (LAION, EmoNet-Voice) is the best new candidate.** Small MLP heads (74M / 148M params)
   that score 40 fine-grained emotions as continuous 0-4 intensities from 24 kHz audio (up to 30 s). CC BY 4.0,
   collection `huggingface.co/collections/laion/emonet`. On its own benchmark the Large model beat Gemini 2.5 Pro
   (Pearson 0.421 vs 0.416); zero-shot 70.6% on EmoDB and 74.2% on RAVDESS. It is small enough for this 16 GB GPU or a
   CPU, and continuous per-emotion scores suit "which take of this line hits the target emotion best". Caveats: trained on
   synthetic voices, tested on acted corpora, taxonomy differs from our 8 families (needs a mapping or a small probe on
   top of its scores), and which encoder sits under the heads is unverified.
3. **Zero-shot audio-LLMs are weak at emotion; a little supervised tuning helps a lot.** VoxEmo (30+ datasets, Qwen2-Audio-7B
   and Audio Flamingo 3): zero-shot below supervised baselines everywhere; LoRA on 0.15% of parameters gave Qwen2-Audio
   +23.7 macro-F1 on average. Transcripts hurt on acted speech (22 of 28 datasets) and help on in-the-wild; complex prompts
   raised parse failures sharply; averaging 5 prompt variants steadied results. Implication: LoRA-tune Qwen2-Audio-7B on our
   136 ear-labelled clips plus the rated generated takes rather than expecting zero-shot to work. With n=136 expect
   modest gains, so hold out by line/event.
4. **Emotion-embedding similarity is unreliable, which matches your emotion2vec experience.** "The False Resonance"
   (arXiv 2604.26347) reports EMO-SIM style metrics are biased by acoustic distractors and misalign with human perception.
   Do not rebuild a reference-similarity metric on any embedding.

## Candidates

| Model | Size / license | Evidence | Fit |
|---|---|---|---|
| EmpathicInsight-Voice Small/Large (LAION) | 74M/148M heads, CC BY 4.0 | beats Gemini 2.5 Pro on EmoNet-Voice bench; 70-74% zero-shot acted | **Try first**: free, small, runs here, continuous scores |
| Qwen2-Audio-7B + LoRA | 7B, Qwen license | VoxEmo: +23.7 macro-F1 with SFT | Try second; fits 16 GB in 4-bit or the Mac in bf16 |
| Audio Flamingo 3 | 7B, NVIDIA non-commercial weights | IEMOCAP UA 76.2%; VoxEmo: steadier format, smaller SFT gain | Usable for a private judge; licence bars shipping anything built on it |
| Kimi-Audio-7B | 7B | MELD 59.1% (their report); licence not confirmed here | Lower priority: big, custom runtime, coarse SER benchmark |
| Vox-Profile (USC) | speech-foundation-model probes; checkpoints "starting to appear on HF" | benchmark of emotion/expressiveness/voice-quality traits | Worth a look for voice-quality tags (breathy, harsh, gravelly); unverified |
| Qwen3-Omni-30B-A3B | 17 GB 4-bit MLX | text-only in MLX per card | Blocked on audio support; see finding 1 |
| emotion2vec, audEERING A/D/V | | user: poor; probe on audEERING embedding reached 46% | Keep the probe as the baseline to beat |

Also: EmoBox (32 corpora, 14 languages) gives a ready evaluation set and training recipes if we want to check a candidate
before using our own labels; but corpora are acted, so our 136 clips remain the deciding test.

## Suggested order

1. Run EmpathicInsight-Voice on the 136 labelled clips, fit a small logistic map from its 40 scores to our 8 families
   (leave-one-out), compare with the 46% probe. Also test within-line ranking of generated takes against the user's emotion
   ratings (per-line Kendall tau; the audEERING probe got +0.35 on 9 lines).
2. LoRA Qwen2-Audio-7B on the labelled clips with a held-out split by line/event.
3. Mac: smoke test first; fallback runtime is PyTorch on MPS.

Needs GPU or Mac time, so nothing has been run.

## Sources
- EmoNet-Voice / EmpathicInsight-Voice: https://arxiv.org/abs/2506.09827 (models: https://huggingface.co/collections/laion/emonet)
- VoxEmo: https://arxiv.org/html/2603.08936
- The False Resonance: https://arxiv.org/pdf/2604.26347
- Audio Flamingo 3: https://arxiv.org/abs/2507.08128
- Kimi-Audio: https://github.com/MoonshotAI/Kimi-Audio
- Vox-Profile: https://arxiv.org/abs/2505.14648
- Qwen3-Omni MLX card: https://huggingface.co/pherber3/Qwen3-Omni-30B-A3B-Instruct-4bit-mlx
- EmoBox: https://github.com/emo-box/EmoBox
