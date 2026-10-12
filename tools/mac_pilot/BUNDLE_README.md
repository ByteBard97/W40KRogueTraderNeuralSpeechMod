# Audio-LLM judge pilot (Mac)

Question: can a large local audio-LLM judge emotion (and voice match) on Abelard clips better than the
free scorer (46% family accuracy from an embedding probe)? Everything here is stdlib Python; the model
runs in a separate server.

1. Start an OpenAI-compatible server that accepts audio (runtime support is unverified, `smoke` tests it):
   `python -m mlx_vlm.server --model mlx-community/Qwen3-Omni-30B-A3B-Instruct-8bit --port 8080`
   (fallback repo: `ZolMik2004/Qwen3-Omni-30B-A3B-Instruct-HybridQuant-MLX`; or llama.cpp `llama-server` with a
   multimodal GGUF). Known issue: audio plus video together crashes in mlx-vlm; audio only should work.
2. `python run_pilot.py smoke` - one clip, then three clips in one request (expect the model to say 3).
   If either fails, stop and try another model; note seconds per clip and peak memory (Activity Monitor).
3. `python run_pilot.py single` then `python run_pilot.py single --transcript` - 136 labelled clips.
4. `python run_pilot.py pair` - both presentation orders for each of the 31 A/B pairs.
5. `python run_pilot.py report` - writes `results/report.json`. Family metrics come out raw and, when the server
   returns logprobs, prior-corrected. Pair verdicts count only when both orders agree; if `data/answers.json`
   is present the report includes agreement with the human answers per axis.

Pass bars: family top-1 clearly above 46% with recall over 0.3 on at least 6 of 8 families; pair agreement
above 75% on the emotion axis with most pairs consistent. Send `results/` back to the Linux box.
Every step resumes where it stopped, so it is safe to interrupt.
