# TTS bake-off — round 1 results (Chatterbox-Turbo vs Qwen3-TTS)

142-line fixed test set (10 unvoiced lines/companion x 13 companions + 12 narrator lines),
zero-shot cloned from the top-scored prompt-bank clip per speaker (real game VO for companions;
a Qwen3-TTS VoiceDesign-generated clip for narrator, since the game has ~no voiced pure-narration
lines to clone from — see `tools/make_narrator_voice.py`).

Scoring: ECAPA-TDNN cosine similarity to the speaker's real-voice centroid (higher = more
"them"; N/A ceiling since even real held-out clips of the same speaker aren't 1.0), word error
rate via faster-whisper small.en vs the source text (lower = more intelligible).

## Overall

| engine | similarity | WER | RTF (measured range) | license |
|---|---|---|---|---|
| Chatterbox-Turbo | 0.640 | 0.097 | ~0.15–0.4x realtime | MIT |
| Qwen3-TTS (Base) | 0.642 | **0.041** | ~0.7–1.4x realtime | Apache 2.0 |

Near-identical voice similarity; Qwen3-TTS is ~2.4x more intelligible (fewer mispronunciations/
dropped words) but noticeably slower — close to or slower than realtime, vs Chatterbox comfortably
faster than realtime. This is why the runtime design leans on graph-lookahead prefetch (synthesize
every reachable next line while the player is still reading the current one) rather than pure
on-demand synthesis: it hides exactly this gap.

## Per speaker (similarity / WER)

See scores.md for the full table. Notable: both engines struggle most on Yrliet (0.60/0.60 sim,
highest WER of the cast) and do best on the narrator (0.83–0.85 sim) and Cassia/Abelard. Pasqal's
low similarity on both (0.52–0.55) is expected — his reference clips are heavily binaric/vox-
processed, not clean speech, which is a bad zero-shot cloning prompt regardless of engine; a
stylized (non-cloned) treatment is probably the right call for him specifically.

## What's next

- IndexTTS-2.5 and Fish S2 envs are built but not yet run through the bake-off (round 2).
- No listening test yet (this is all objective metrics) — a blind A/B page for the user + friends
  is still open, and matters more than these numbers for a final pick: WER and ECAPA similarity
  don't capture "does it sound like a professional voice actor," only "intelligible" and
  "acoustically close."
- Chatterbox's paralinguistic tags ([laugh], [sigh], etc.) and Qwen3's instruct-text path haven't
  been exercised yet — this round used plain text, no annotation. The annotation pipeline
  (tools/annotate) is a separate, working track; the two haven't been combined yet.
