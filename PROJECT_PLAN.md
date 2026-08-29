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
- [x] TTS bake-off infra + first two engines fully run: chatterbox_turbo (142/142,
      sim=0.622 wer=0.100) and qwen3_tts (142/142). IndexTTS-2.5 and fish-speech envs built,
      not yet run through the bake-off.
- [x] Gold annotation set: 255 hand-checked lines (14 conversations, all companions + narrator),
      data/annotations/gold.json. compare_to_gold.py scorer written.
- [x] **Runtime mod fork**: src/RogueTraderNeuralSpeechMod, forked from Osmodium SpeechMod (MIT,
      attribution preserved in LICENSE-SpeechMod-upstream.txt). Builds clean (0 errors) against
      game DLLs and deploys via `dotnet build -t:Deploy`. NeuralSpeech (ISpeech impl) + 
      NeuralVoiceUnity (UnityWebRequest -> sidecar -> AudioClip) replace the SAPI/`say` backends;
      same platform now works everywhere. v0.1 scope: routes through upstream's 4 VoiceType
      categories (Narrator/Female/Male/Protagonist), NOT yet per-character (Heinrix-as-Heinrix)
      voices - that needs a new ISpeech entry point taking a speaker GUID, next up.
      NOT YET RUN IN-GAME (compiles + deploys only; no game launch since the export run).
- [x] **TTS sidecar**: src/TtsSidecar/server.py (FastAPI), lexicon.py (applies data/lexicon),
      annotation_bridge.py (neutral schema -> per-engine directives), GUID+content-hash disk
      cache. Engine adapters shared with the bake-off harness at tools/tts_engines/. NOT YET
      SMOKE-TESTED end-to-end (GPU was saturated by bake-off runs when written).

### Next (rough order)
- [ ] Smoke-test the sidecar end-to-end (start it, curl /synth, confirm cache hit/miss)
- [ ] Score qwen3_tts bake-off; run IndexTTS-2.5 + fish-speech through the bake-off; build a
      blind A/B listening page for the user + friends
- [ ] Bulk annotation pass (local models, sharded across Linux 5080 + Mac M4 + Windows 4070),
      validated against the gold set via compare_to_gold.py before trusting it
- [ ] Spike: is Unity audio enabled in-game? (the mod assumes yes; untested) - decides whether
      NeuralVoiceUnity's AudioSource approach works or needs a Wwise external-source swap
- [ ] Per-character voice routing: new ISpeech method taking a speaker GUID (not just VoiceType),
      wired through Dialog_Patch/BarkPlayer_Patch/DialogAnswerBaseView_Patch, sidecar voice map
      keyed by data/voices/prompts/prompts.json
- [ ] First actual in-game test (requires launching the game - check with user first)
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
