# TTS bake-off - round 1 results (Chatterbox-Turbo vs Qwen3-TTS vs IndexTTS-2.5)

142-line fixed test set (10 unvoiced lines/companion x 13 companions + 12 narrator lines),
zero-shot cloned from the top-scored prompt-bank clip per speaker (real game VO for companions;
a Qwen3-TTS VoiceDesign-generated clip for narrator, since the game has ~no voiced pure-narration
lines to clone from - see `tools/make_narrator_voice.py`).

Scoring: ECAPA-TDNN cosine similarity to the speaker's real-voice centroid (higher = more
"them"; N/A ceiling since even real held-out clips of the same speaker aren't 1.0), word error
rate via faster-whisper small.en vs the source text (lower = more intelligible).

## Overall

| engine | similarity | WER | RTF (measured range) | license |
|---|---|---|---|---|
| Chatterbox-Turbo | 0.640 | 0.097 | ~0.15–0.4x realtime | MIT |
| Qwen3-TTS (Base) | 0.642 | **0.041** | ~0.7–1.4x realtime | Apache 2.0 |
| IndexTTS-2.5 | 0.628 | 0.067 | ~0.5–1x realtime | weights non-commercial |

All three cluster within ~0.014 similarity of each other - inside noise for ECAPA cosine at
n=142, i.e. not a real discriminator between these three. WER is the one measurement that
actually separates them: Qwen3-TTS is ~1.6x more intelligible than IndexTTS-2.5 and ~2.4x more
than Chatterbox. Speed favors Chatterbox comfortably, IndexTTS-2.5 sits in the middle, Qwen3-TTS
is the slowest - at or below realtime. This is why the runtime design leans on graph-lookahead
prefetch (synthesize every reachable next line while the player is still reading the current
one) rather than pure on-demand synthesis: it hides exactly this gap regardless of which engine
ships.

IndexTTS-2.5's weights are non-commercial-only, which conflicts with a free public mod release
built from them; it stays as a reference point but isn't a release candidate as-is.

**Fish Audio S2 was dropped from the bake-off** before completing a full run: its license is
also non-commercial, it's the largest of the four models, and its smoke test hung indefinitely
holding ~7-9 GB of VRAM without producing output. On an axis (similarity) where the top three
engines already differ by only 0.014, a fourth non-commercial, unreliable entrant wasn't worth
chasing further; that VRAM is better spent on the annotation workers.

## Per speaker (similarity / WER)

See scores.md for the full table. Notable: all three engines struggle most on Yrliet (~0.60
sim, highest WER of the cast) and do best on the narrator (0.83–0.85 sim) and Cassia/Abelard.
Pasqal's low similarity across the board (0.52–0.55) is expected - his reference clips are
heavily binaric/vox-processed, not clean speech, which is a bad zero-shot cloning prompt
regardless of engine; a stylized (non-cloned) treatment is probably the right call for him
specifically.

## What's next

- No listening test yet (this is all objective metrics) - a blind A/B page for the user + friends
  is still open, and matters more than these numbers for a final pick: WER and ECAPA similarity
  don't capture "does it sound like a professional voice actor," only "intelligible" and
  "acoustically close." Given how close the objective numbers are, the listening test is now the
  actual tiebreaker, not a confirmation step - plan to run it before locking the default engine.
- Chatterbox's paralinguistic tags ([laugh], [sigh], etc.) and Qwen3's instruct-text path haven't
  been exercised yet - this round used plain text, no annotation. The annotation pipeline
  (tools/annotate) is a separate, working track; the two haven't been combined yet.
- Default-engine candidates for public release are therefore Chatterbox-Turbo (MIT) and
  Qwen3-TTS (Apache 2.0) - both fully permissive; IndexTTS-2.5 stays evaluation-only under its
  current license.
