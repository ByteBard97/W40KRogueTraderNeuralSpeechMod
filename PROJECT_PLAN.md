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
- [x] **8B annotation quality investigated and found wanting - now switching to 14B+bios.**
      Manually spot-checked real 8B output against source text and found genuine tone-inversion
      errors, not just defensible disagreements: a devout "God-Emperor's blessing" declaration
      tagged `amused`; Marazhai (a sadistic Drukhari) quietly relishing a torture victim's pain
      tagged flat `neutral`. Root-caused part of this: the annotator only ever saw a bare speaker
      name, with zero character context - fixed by generating
      `data/character_bios.json` (21 companion bios, mined from data/strings.enGB.json codex/
      backstory text, cross-checked via script.json units and websearch for ambiguous cases -
      "Stranger"=Trazyn incognito, "Manipulus"=Eogunn's Mechanicus title, "Overseer"=generic
      stock role) and wiring per-chunk bio injection into tools/annotate/annotate.py. Bios only
      cover ~18% of lines though (8,528/47,799) - the other 82% are `default_speaker` lines the
      offline export can't attribute to a specific companion, which is exactly where the "amused"
      miss above occurred, so bios alone can't fix most of the corpus.
      Tested 14B vs 8B (both +bios) directly on the two flagged examples: 14B fixed both cleanly
      (Emperor line -> reverent neutral; Marazhai -> correctly menacing/amused) while 8B+bios
      fixed them too but introduced a new miss nearby (tagged a sympathetic question "Who are
      you and what happened to you?" as `commanding`) - 8B tends to over-apply a bio's dominant
      trait indiscriminately, 14B balances it against actual line content better. Aggregate gold
      score moved only modestly (emotion_match 0.517->0.537) - exact-match doesn't distinguish
      "sounds broken" from "defensible disagreement," so the targeted before/after check on real
      flagged lines was the check that actually mattered here.
      **Corrected an earlier mistake**: a prior "~22 tok/s, genuine hardware ceiling, ~28-30h ETA"
      claim was wrong. That number was measured while diagnostic test calls were running
      concurrently with the live production worker (ollama can serve overlapping requests, so
      both were genuinely competing for the same GPU compute, not just queueing) - own diagnostic
      testing was quietly slowing down the real bulk run for parts of this session. Clean,
      uncontended, repeated measurements on realistic ~18-30 line chunks: qwen3:8b ~135 tok/s,
      qwen3:14b ~81 tok/s on the RTX 5080. At ~77 output tokens/line and 47,799 total lines, a
      full-corpus 14B+bios run across both existing GPUs (5080 + 4070) is roughly **8-13 hours**
      of generation time - both machines now restarted on 14B+bios into fresh cache dirs
      (`cache_14b`, `cache_win_14b`; the old 8B caches are left alone as a fallback, not deleted)
      for a full from-scratch redo, since the quality problem exists in already-annotated lines
      too, not just the unfinished remainder. This makes the earlier Mac + 32B plan optional
      rather than necessary - revisit only if 14B+bios quality still isn't good enough once more
      of it can be reviewed.
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
- [x] **Exercised the full annotation -> sidecar -> Chatterbox pipeline against real 14B+bios
      output**, not just plain text. Confirmed end-to-end: real annotated lines (fear+gasp,
      sarcastic+sniff) POSTed to a live `/synth` correctly produced tagged text
      (`[fear] [gasp] ...`) with intensity-scaled `exaggeration`, and returned valid WAV audio
      (HTTP 200, correct duration) - the wiring built earlier in the session works for real, not
      just in isolated unit tests.
      **Found and fixed a real bug in the process**: `data/lexicon` respelling glued onto a
      following hyphen in compound terms ("vox-system" -> "vokss-system" instead of "vokss
      system") - affects 54 distinct hyphenated compounds across the corpus (Vox-, Chaos-,
      Omnissiah-, Administratum-branded terms, etc.), not just one line. Root cause: `\b` is a
      word/non-word boundary, and `-` counts as non-word, so `\bTERM\b` already matched cleanly
      inside a hyphenated compound but left the hyphen attached to the respelling with no space.
      Fixed in src/TtsSidecar/lexicon.py: the regex now optionally consumes a trailing hyphen
      before a word character and replaces it with a space instead, for both `respell()` and
      `ipa_ssml()`. Verified against the original case and spot-checked real corpus lines.
      Also confirmed (no bug found): narration-tag stripping (`{n}...{/n}`) is already handled
      correctly and differently for the two real cases - `speech_only()` for companion dialogue
      lines (drops narration, bake-off/bare test-set use) vs `narration_only()` for pure-narration
      lines (keeps the descriptive text, strips only the markup) - and the live C# mod never sees
      raw `{n}` markup at all, since the game's own renderer already converts it to `<i><color=...>`
      tags before `DisplayText`, which `NeuralSpeech.cs`'s existing tag-stripping already handles.
- [x] **Exercised the cache-merge -> deploy -> runtime-lookup path end-to-end for the first time**,
      against real partial-run data (this had never been run before - the annotation pipeline had
      produced cache files but nothing had ever combined them into the file the mod actually
      reads). Linux `cache_14b` (500 conversations) and Windows `cache_win_14b` (326, pulled via
      scp from `C:/RTBuild/annotate/data/annotations/cache_win_14b`) have zero filename collisions
      (disjoint by design, sharded by conversation guid hash) and combined cleanly into 826
      conversations / 25,900 annotated lines via `annotate.py --merge`. Copied the merged file to
      `src/RogueTraderNeuralSpeechMod/Voice/annotations.enGB.json`, built with
      `dotnet build -t:Deploy`, and confirmed the csproj's conditional `CopyToOutputDirectory` +
      Deploy target actually landed the 6.5MB file in the live UMM mods folder. Statically
      verified the runtime path is sound without needing to launch the game (avoids GPU
      contention with the still-running annotation workers): `AnnotationStore.cs` passes records
      through as raw `JObject`s (no hand-written C# schema to drift out of sync), and
      cross-checking all 25,900 annotation guids against `conversations.enGB.json`'s `text_key`
      values showed a 100% match - every annotation the pipeline produced resolves to a real
      dialogue cue, confirming the guid space used by `annotate.py` (`text_key`) is exactly the
      one `AnnotationStore.Resolve(cueGuid)` looks up at runtime
      (`DialogController.CurrentCue.Text.Key`). Both workers remained running throughout (Linux
      500, Windows 326, unaffected by the local file copy/build side of this).
- [x] **Resolved a licensing open question ahead of the voice-clone builder tool**: researched
      whether `tools/bin/wwiser.pyz` and `vgmstream-cli`, both currently used by the dev-only
      extraction scripts, can legally be bundled in a future release zip. **vgmstream is ISC
      (permissive) with official prebuilt CLI binaries for Windows/macOS/Linux** - bundling is
      safe once expanded attribution (added to README.md) is included, though the LGPL
      components it links (mpg123, FFmpeg) should be confirmed dynamically-linked before
      shipping a build. **wwiser has no LICENSE file at all** - reverse-engineered by bnnm with
      no explicit grant of redistribution rights, so it must NOT be vendored in a release zip;
      the builder tool will need to link users to the upstream repo for a self-download, or
      contact bnnm for explicit permission. Confirmed neither binary is currently tracked in git
      (both correctly covered by the `bin/` gitignore pattern already) - no existing exposure.
- [x] **Sanity-checked the real bulk 14B+bios output against the user's own explicit concern**
      ("sample a bunch of different parts... since 8B models are not that smart") - a subagent
      pulled a stratified 78-line sample (69 conversations, 30 speakers, all 12 emotions
      represented) from the actual 826-conversation merged output, not just the small curated
      gold set. Verdict: acceptable quality (~88% clean), calibration is excellent (99.7% of
      "neutral" records land inside the prompt's own 0.1-0.35 target band), and bio-matching is
      often sharp (Marazhai and Trazyn both nailed their bios' cold, mocking register). **Found
      one real, quantified, systematic defect**: the discrete `emotion` enum disagrees with
      clearly sarcastic/mocking language in the model's own free-text `instruct` field on ~2% of
      all lines (worst case: Marazhai's calm, purring threats tagged `fear` instead of
      `sarcastic`) - a TTS backend keying off the enum alone would render these backwards.
      **Fixed** with a keyword-based reconciliation pass (`reconcile_sarcasm_emotion` in
      `tools/annotate/annotate.py`, run automatically as part of `--merge`) rather than
      re-running the model: any line whose `instruct` text contains sarcasm/mockery/condescension
      language gets its `emotion` corrected to `sarcastic` unless already `sarcastic`/`amused`.
      Verified against the two exact examples the review flagged (Marazhai's Oghyr-traps line,
      Enforcer Klein's "up your arse" line) - both now read `sarcastic` as expected. Re-merged
      (830 conversations, 26,293 lines, 278 lines corrected - ~1.06%, consistent with the
      sampled estimate) and redeployed to the live mod folder. Minor remaining issues noted but
      not worth a full re-run: rare (0.12%) garbled self-referential instruct text, and a couple
      of lines where a companion's pure-narration line still gets a spoken-voice instruct because
      the speaker field isn't literally "narrator" - low-severity, revisit if they show up in the
      listening test.
      **Self-caught a false-positive problem in the fix itself**: the first version also matched
      on bare "mocking"/"mockery", which sounded like the same signal but wasn't - auditing the
      actual 278-line delta (not just resampling the already-correct "sarcastic" population,
      which is what the first spot-check mistakenly did) turned up real misfires, e.g. a defiant
      "Anger is power" challenge and a cackling, unhinged "reveling in their own madness" rant
      both got flattened from `angry`/`dramatic` into `sarcastic`, because mocking language
      coexists with genuine rage or mania just as often as calm sarcasm. Narrowed the keyword set
      to just `sarcastic`/`sarcasm`/`condescending`/`condescension` - i.e. only when the model's
      own instruct text explicitly names the read and then contradicts itself in the enum, which
      is the actual bug. Re-merged with the narrower rule (833 conversations, 26,494 lines, 92
      corrected this time) and manually reviewed all 92 by source emotion (57 neutral, 30 angry,
      2 sad, 1 each dramatic/happy/fear) - every one now has explicit "sarcastic"/"condescending"
      language in its own instruct text with no remaining false positives found. Redeployed.
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
