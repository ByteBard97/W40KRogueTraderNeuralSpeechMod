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

### In progress
- [ ] **TTS bake-off**: Chatterbox-Turbo (installed, running first), Qwen3-TTS (downloaded),
      IndexTTS-2.5, Fish S2. Output: per-companion similarity/WER/RTF table + listening page.
- [ ] qwen3:8b pulled for annotation; gold-set prompt design next

### Next (rough order)
- [ ] Score bake-off, build blind A/B listening page for user + friends
- [ ] Annotation gold set (~200 lines, frontier model) → bulk pass (local, sharded across
      Linux 5080 + Mac M4 + Windows 4070) → review pass
- [ ] 40K lexicon v1 from vocab worklist (top ~300 terms; IPA + respelling columns)
- [ ] Spike: is Unity audio enabled in-game? (tone-playing test mod) → decides IAudioOutput
- [ ] Runtime mod: fork SpeechMod hooks, sidecar client, prefetch + cache
- [ ] Sidecar server: FastAPI/raw-socket, engine adapter, voice map, cache
- [ ] Default-speaker resolution join (15,544 cues) for per-NPC voices
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
