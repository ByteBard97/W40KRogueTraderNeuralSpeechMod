# Project Plan — Rogue Trader Neural Speech Mod

Living document. Any session (or agent) picking this project up starts here.

## Goal

Voice the ~90% of Warhammer 40,000: Rogue Trader that ships unvoiced, with **live, local,
neural TTS**: per-character cloned/designed voices, emotion-annotated delivery, working on
Linux/Proton and Windows. Publish free on Nexus + GitHub. Never distribute cloned voice data —
an opt-in local tool builds voice references from the *user's own* game files.

## Architecture (decided)

1. **Runtime mod (C#/UMM)** — fork of Osmodium SpeechMod's hook layer (MIT).
   New seam: `ITtsBackend` (text+speaker+annotation → PCM) and `IAudioOutput` (PCM → speakers).
   Voiced lines (Sound.json / `LocalizedString.GetVoiceOverSound`) always win — no double narration.
   Latency plan: graph-lookahead prefetch (synthesize all reachable next cues while the player
   reads), GUID-keyed disk cache, sentence-split streaming for cold lines.
2. **TTS sidecar (Python, GPU, localhost)** — engine chosen by bake-off (see below); voice map
   `speaker_guid → voice prompt/embedding`; translates neutral annotations per engine.
3. **Offline pipelines (this repo, already working)** — dialogue-graph export → ordered
   conversations → LLM emotion annotation → `annotations.<locale>.json`; 40K phonetic lexicon;
   voice-line extraction → prompt banks.

## Status

### Done
- [x] Research: prior art (SpeechMod, AIVO, Ripcy), verified hook points and blueprint schema
- [x] `DialogueExporter` UMM mod builds on Linux (.NET 8 at ~/.dotnet), dumps full dialogue graph
- [x] Localization extraction: 77,691 strings; 5,089 voiced (6.6%); vocab worklist (8,348 terms)
- [x] Ordered conversations: 1,329 dialogs / 31,572 text cues (9.7% voiced); speakers attributed
- [x] Voiced-line audio extraction: 5,188 speaker-attributed WAVs (companions 30–105 min each)
- [x] Prompt banks (top-12 scored clips/speaker) + fixed 142-line bake-off test set
- [x] Bake-off + scoring harness (ECAPA similarity + Whisper WER); annotation harness
      (ollama/claude/kimi backends, constrained schema, resumable cache, shardable)

- [x] Default-speaker resolution: 2,866/15,544 resolved by within-dialog majority vote;
      documented ceiling (~7,297 cues are dynamic-NPC templates, unresolvable offline - same
      limitation AIVO hit; runtime CurrentSpeaker resolution is the real fix, see memory)
- [x] 40K/RT pronunciation lexicon v1 (191 terms, IPA + respelling) at data/lexicon/lexicon.json
- [x] TTS bake-off complete for the three license-clean/reference candidates: chatterbox_turbo
      (sim=0.640, wer=0.097, MIT), qwen3_tts (sim=0.642, **wer=0.041 best**, Apache 2.0),
      indextts2 (sim=0.628, wer=0.067, weights non-commercial - reference only, not a release
      candidate). All three cluster within ECAPA noise on similarity; WER and speed are the
      real discriminators. Fish Audio S2 was dropped before completing a run: non-commercial,
      largest model, smoke test hung indefinitely holding 7-9 GB VRAM for zero payoff on an
      axis that doesn't discriminate between engines anyway. See data/bakeoff/RESULTS.md.
- [x] Gold annotation set: 255 hand-checked lines (14 conversations, all companions + narrator),
      data/annotations/gold.json. compare_to_gold.py scorer written. Tracked so far:
      qwen3:8b_no_think emotion_match=0.470, qwen3:8b_calibrated=0.517 (after adding explicit
      neutral-bias calibration to the SYSTEM prompt - see data/annotations/gold_comparison.md).
      claude-haiku-cli comparison tried and abandoned: `claude -p` keeps its assistant persona
      even with --restricted --strict-mcp-config (can refuse a prompt it reads as suspicious)
      and has no constrained decoding (JSON extracted from prose, 2/2 gold conversations failed
      outright vs zero failures from the ollama bulk run so far) - worse fit for unattended bulk
      classification regardless of any accuracy difference. See gold_comparison.md. Sticking
      with qwen3:8b_calibrated.
- [x] **Sidecar smoke-tested end-to-end**: /health, /voices, /synth (incl. annotation-driven
      synthesis and GUID+content-hash cache hit/miss) all verified working.
- [x] **Unity-audio spike resolved (was the biggest open risk)**: confirmed via UnityPy against
      `globalgamemanagers` that `AudioManager.m_DisableAudio = True` - Unity's own audio engine
      is off in this game (Wwise-only title), so the original NeuralVoiceUnity design
      (AudioSource/AudioClip) would have been silently silent in-game. Fixed by bypassing both
      Unity and Wwise audio entirely: NativeAudioPlayer (Voice/NativeAudioPlayer.cs) plays WAVs
      straight to the OS device - MCI (winmm.dll) on Windows/Proton (Wine implements winmm
      completely, so this works unmodified under Proton), afplay/paplay/aplay subprocess on
      macOS/native Linux. NeuralVoiceUnity now fetches raw bytes via UnityWebRequest (unaffected
      by disabled Unity audio - it's networking, not audio) and hands the WAV to
      NativeAudioPlayer instead of AudioSource.Play(). Not yet verified with real audio hardware
      in a live game session (see Next).
- [x] **Per-character voice routing**: ISpeech gained `SpeakAsCharacter(text, blueprintGuid,
      fallbackVoice, delay, cueGuid)`. Voice/speaker_map.json (generated from data/raw/
      script.json's per-unit character_name, cross-referenced against the prompt bank) maps
      21/22 known companions' blueprint AssetGuid -> prompt-bank speaker name (only "Manipulus"
      unmatched - name-collision, falls back to gender voice). Keyed on AssetGuid, not the
      localized CharacterName, so it survives non-enGB locales. Wired into Dialog_Patch (via
      NeuralSpeech.SpeakDialog, which now resolves DialogController.CurrentSpeaker's blueprint
      guid before falling back to gender-based routing) and BarkPlayer_Patch (bark speaker's
      own guid, same fallback chain).
- [x] **Runtime annotation plumbing wired** (was previously a dead end - NeuralVoiceUnity only
      sent {text, speaker}): NeuralVoiceUnity/NeuralSpeech now thread a `cueGuid` through
      SpeakDialog/SpeakAs/SpeakAsCharacter, and AnnotationStore.cs looks it up in a shipped
      Voice/annotations.enGB.json (same load pattern as speaker_map.json - gracefully absent
      until the bulk annotation pass below is merged and copied in). The sidecar's /synth
      already expected {cue_guid, annotation}; this closes the gap on the C# side.
- [x] **Runtime mod fork**: src/RogueTraderNeuralSpeechMod, forked from Osmodium SpeechMod (MIT,
      attribution preserved in LICENSE-SpeechMod-upstream.txt). Builds clean (0 errors, verified
      on both Linux and native Windows) against game DLLs and deploys via `dotnet build
      -t:Deploy`.
- [x] **First live in-game audio test: PASSED.** Added a `speech_test.request` control-file
      self-test to Main.cs (mirrors DialogueExporter's pattern): on an unattended launch it fires
      SpeakPreview (narrator) and SpeakAsCharacter (a known companion) a few seconds after load,
      logs results, and quits. Round 1 caught a real bug: two concurrent Speak() calls wrote to
      the same fixed temp WAV path, and MCI holding the first file open for playback caused an
      `IOException: Sharing violation` on the second write - a real race that would hit in normal
      play (overlapping bark + dialogue line, quick successive answers), not a test artifact.
      Fixed with a unique GUID-named temp file per request (NativeAudioPlayer deletes the
      previous one once its device is closed). Round 3 (after also fixing ambiguous logging)
      confirmed clean: `Player.log` shows `NativeAudioPlayer: MCI open rc=0 play rc=0` for both
      calls, on two distinct files, no exceptions - the full chain (sidecar HTTP -> WAV bytes ->
      unique temp file -> winmm MCI under Proton) works end-to-end.
- [x] **TTS sidecar**: src/TtsSidecar/server.py (FastAPI), lexicon.py (applies data/lexicon),
      annotation_bridge.py (neutral schema -> per-engine directives), GUID+content-hash disk
      cache. Engine adapters shared with the bake-off harness at tools/tts_engines/.

### Next (rough order)
- [ ] **Bulk annotation pass in progress**: 1,329 conversations, sharded Linux (RTX 5080,
      qwen3:8b via ollama) + Windows (RTX 4070, same model). Caught and fixed a real bug at
      ~10% through the corpus: the recursive halving-retry (for when the model drops a guid)
      was capped at depth 3, which for the long tail of large conversations (50 run >200 lines;
      the biggest, a multi-companion epilogue montage, runs 1,363) never reaches a small enough
      chunk to reliably succeed - those conversations failed permanently, every time, on both
      machines. Fixed in tools/annotate/annotate.py: conversations are now pre-chunked to <=30
      lines up front, and the retry-halving is bounded by chunk size (down to 2 lines) rather
      than depth, so it can't give up early regardless of how long the conversation is. Verified
      against the two known-bad conversations before rolling out; both workers restarted with
      the fix (cache-file resumability means only previously-failed conversations need to
      re-run). Once complete: `--merge`, sample-check against compare_to_gold.py, and copy the
      merged file to src/RogueTraderNeuralSpeechMod/Voice/annotations.enGB.json so it ships (the
      csproj's copy-item is already conditioned on that file existing).
- [ ] Have an actual human (the user) confirm they can HEAR the test lines - the automated
      self-test confirms MCI returns success codes, which is strong evidence but not literally
      the same as a human ear on real speakers. Cheap: run `speech_test.request` again without
      the "quit" content and stay at the main menu to listen.
- [x] **Blind A/B listening page built**: tools/listening_test/ (serve.py + index.html +
      tally.py). Local-only HTTP server (never a published Artifact - it serves voice-cloned
      audio from the user's own game files, which must not be distributed): presents each of the
      142 bake-off lines with Chatterbox-Turbo and Qwen3-TTS clips in randomized, unlabeled A/B
      order, records votes to data/bakeoff/listening_votes.jsonl (gitignored, resumable via
      localStorage progress tracking), tally.py un-blinds and reports win/tie rates overall and
      per speaker. Smoke-tested end-to-end (server, pairing, audio serving, voting, tallying) -
      not yet actually run by a human. This is now the real tiebreaker: run it and tally before
      locking the default engine.
- [ ] Exercise Chatterbox's paralinguistic tags / Qwen3's instruct-text path against real
      annotation output (currently bake-off used plain text only; the two pipelines haven't been
      combined yet).
- [ ] Later: user-side voice-clone builder tool; Windows packaging; Nexus/GitHub release

## Environment
- Linux (this box): game + Proton prefix paths in `Directory.Build.props`; RTX 5080 16 GB;
  `.venv-tts` = cu128 torch + engines. Game launches for exports: unattended main-menu runs OK.
- Windows build/test box: `SSH access` (PowerShell; dotnet, git, python, RTX 4070).
- Mac M4 24 GB available as annotation worker (ollama).

## Rules
- git identity: bytebard97 <bytebard97@users.noreply.github.com>; no AI attribution in commits
- never push without explicit ask; never distribute game-derived audio or cloned voices
- data/voices/, data/raw/, reference/ stay out of git
