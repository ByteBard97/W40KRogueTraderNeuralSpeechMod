# Brief: replaced voice audio is silent in-game (Rogue Trader + AIVO Wwise banks)

Written 2026-10-11 for a second opinion. Everything below was verified from files and logs unless marked "unverified".

## The problem

We replaced the audio inside the AI Voiceover (AIVO) mod's Wwise soundbank with our own generated speech (new narrator
voice plus named-speaker clones). In game, the user has not heard a single replaced clip. Lines we did not replace play
their original AIVO audio normally. The replaced ones, including all narrator lines, are silent. No crash, no error.

## Setup

- Game: Warhammer 40,000: Rogue Trader (Unity 6, Wwise SDK 2022.1.19), run on Linux under Proton.
- Mod loader: UnityModManager (UMM) with Harmony. AIVO (UMM id `W40KAIVO`, by pas2k, v0.2.0) loads every `*.bnk` in
  `UnityModManager/W40KRT_AIVOMod/soundbanks/` into Wwise and plays events named `ev_<cue guid>` through
  `AkSoundEngine`. It also logs `Allowing ev_...` / `Blocking ev_...` per event in `Player.log`.
- The original voice pack is one 3.1 GB bank (`w40krt_avio_charvogen.bnk`, Vorbis wems, Wwise bank version 145).
- Our tool `tools/bnk_patch/{bank,wem,patch}.py` rewrites the bank:
  - Per replaced Sound object it sets the codec plugin id to `0x00010001` (PCM) and the in-memory media size to the new
    wem size; the rest of HIRC is byte-identical.
  - New audio is 24 kHz mono 16-bit PCM wem (RIFF, `fmt ` size 16, format tag 1), about -20 LUFS.
  - Replaced media is removed from the main bank's DIDX and written into media-only side banks
    (`_pcm1.bnk`, `_pcm2.bnk`, `_pcm3.bnk`: BKHD + DIDX + DATA, no HIRC), because a bank DATA chunk cannot exceed
    u32 (~4 GB). Side bank ids are 609496937, 609496938, 609496939; main bank id 989035913.
  - Design assumption: Wwise resolves media ids across all loaded banks, so events in the main bank find media in
    the side banks.
- Installed now: main 1.9 GB + pcm1 3.4 GB + pcm2 3.4 GB + pcm3 2.0 GB (about 10.7 GB total), 12,475 clips replaced
  (6,789 narrator + 5,750 named-speaker + the rest of the merged set), 143 clips have no bank event.

## What we verified

- `Player.log` shows all four banks load: `Bank loading ...: AK_Success` (main, pcm1, pcm2, pcm3).
- I parsed the installed banks with our reader. For four flagged narrator events (`2d5e736b...`, `cb3f1b83...`,
  `a4e47895...`, `d976ffbc...`): event -> action -> Sound exists; plugin `0x10001`, stream flag 0 (in memory), source
  media id found in exactly one bank (pcm1 or pcm3), size equals the HIRC size, RIFF header sane, 12 to 25 s long,
  RMS about 3,700 (about -19 dBFS), peaks near full scale. So the data is present and not silent on disk.
- A diagnostic mod (Dialogue Flag, our own UMM mod, Harmony postfix on
  `VoiceOverPlayer.PlayVoiceOver(string, MonoBehaviour|GameObject)`) logged every voice event the game started. The
  narrator events appear (target object `None`, no speaking character), and `VoiceOverStatus.IsEnded` stays false,
  i.e. the game thinks they are playing. AIVO logged `Allowing` for them. The user heard nothing.
- Unreplaced lines (e.g. a female NPC, Jae, who is not in our render set) play, in the original male-sounding AIVO
  voice. So the output path, volume and AIVO's hook are working for Vorbis wems from the main bank.
- 120 of 127 voice events in the first session were not in our render set at all (named NPCs we have not rendered, crowd
  barks), so most of what the user heard was expected to be the old audio. Only 7 played events were ours: 5 narrator, 1
  Argenta, 1 Cassia. The user says none of those sounded new.

## What differs from a session that worked

- On 2026-10-07 (before the narrator rework) the user played 1 to 2 hours with an earlier build of the same format
  (main + pcm1 + pcm2, 10,966 clips, 24 kHz PCM) and reported no silence or static. The only structural differences
  since then:
  - a fourth bank (pcm3) and about 1.7 GB more total media;
  - the main bank is now only 1.9 GB;
  - the user installed other UMM mods on 2026-10-10 (ToyBox, EnhancedGraphics, Faster Loading Times, MicroPatches,
    Scaling Fix, Better Type Sorting, Allow Modded Achievements, Atlas Upscale);
  - AIVO's Info.json was restored to the original (v0.2.0).
- Our own older speech mod (UMM id `W40KRT_NeuralSpeechMod`, plays generated speech from a sidecar) was enabled during
  the first test. Notes said to keep it disabled. It is disabled for the second test (Params.xml `Enabled="false"`).
  Result of the second test: still silent for the narrator.
- Caveat: the 2026-10-07 test may not have exercised narrator-type lines (no speaking object) at all, and that earlier
  narrator content was the wrong voice, so "worked" there is only about named-speaker lines. Unverified.

## Hypotheses, ranked by my guess

1. Something about PCM media in side banks is not actually played by Wwise in this setup (for example in-memory PCM
   source plus a streamed/zero-size field, a required wem chunk we omit, or media resolved from a bank without a
   matching HIRC), and the 2026-10-07 "worked" report was really the user hearing unreplaced Vorbis lines or not
   noticing. A decisive test is a single audible tone or "test" clip.
2. Posts are rejected (playing id 0) or stopped immediately by another mod (AIVO's `InterruptPlaybackOnPlay` is true,
   `SoundDedupTimeout` 4, `PlaybackBarks` true) before any sound comes out.
3. A mod added on 2026-10-10 interferes with bank loading or voice playback (Faster Loading Times and MicroPatches are
   the likeliest).
4. Resource limits with 10.7 GB of banks loaded (game RSS was 5.4 GB with the banks loaded; machine has 61 GB RAM, so
   not plain OOM, but Wwise media pool limits are unverified).
5. Narrator events have no emitter object (`target None`), so Wwise has no game object to play on (unverified; the
   original AIVO bank also covers these lines, and we do not know whether the user ever heard them).

## Debug instrumentation just added (not yet run)

`tools/dialogue_flag/AudioDebug.cs`, installed in the Dialogue Flag mod, writes `audio_debug.log` in the mod folder.
It Harmony-patches `AkSoundEngine` by reflection:

- every `PostEvent` whose event name starts with `ev_`: arguments, caller frames (assembly!type.method), and the
  returned playing id (0 is flagged as rejected);
- `StopPlayingID`, `StopAll`, `ExecuteActionOnEvent` with callers;
- `LoadBank`/`UnloadBank`;
- `SetRTPCValue` changes (first 300);
- on the first voice post, the owners/priorities of all Harmony patches on `AkSoundEngine`, `VoiceOverPlayer` and
  `SoundEventsManager`.

## Questions for the reviewer

1. In Wwise 2022.1 bank version 145, is a Sound object with plugin `0x00010001` and stream type 0 sufficient for an
   in-memory PCM wem, or does the source need other fields (for example the `fmt ` extensible form, a `DATA`/loop
   chunk, `bIsLanguageSpecific`, or prefetch size)? What does Wwise do when the media id lives in another loaded
   bank's DIDX?
2. Can media-only banks (no HIRC) be loaded with `LoadBank` and have their DIDX served to events from another bank?
   Are there known issues with several such banks or with ids that collide?
3. Other places to log or test that would separate "event rejected" from "played but silent" (Wwise profiler capture
   over the network, `AkCallbackType`, bus meters)?
4. Any known interaction between AIVO's Harmony patches and other UMM mods that could swallow our events?

## Files

- `tools/bnk_patch/bank.py`, `patch.py`, `wem.py`: the bank rewriter.
- `tools/dialogue_flag/`: the diagnostic mod (`Main.cs`, `Patches.cs`, `AudioDebug.cs`).
- Game logs: `.../Owlcat Games/Warhammer 40000 Rogue Trader/Player.log` and `GameLogFull.txt`.
- Rollback: previous bank sets are in `UnityModManager/W40KRT_AIVOMod/soundbanks_disabled/` (move files, never delete).

## Resolution (2026-10-11, same day)

Cause found by tone tests in game: Wwise 2022.1's PCM codec only plays **WAVE_FORMAT_EXTENSIBLE** wems (fmt tag 0xFFFE,
40-byte fmt chunk, subformat PCM, channel mask 0x4 for mono). Our plain tag-1 PCM (16- or 18-byte fmt chunk) was silent, which
explains every silent replaced line since 2026-10-06, including the 10-08 Pasqal/Idira reports. Not the cause: side banks
(extensible tones played from the main bank and the side bank alike, wiring through a re-pointed Sound object played the
other line), mod interference, AIVO's stop events, the narrator having no emitter object. The 2026-10-07 "worked" report
was never valid (the 10-08 handoffs record the silence). Fix: `tools/bnk_patch/wem.py` writes the extensible header; the
user confirmed the real BG3 narrator and named-speaker clips play. Process lesson: tone-test any codec/header change in
game before a bulk build (memory: prove-audio-format-in-game-first).

Follow-ups done the same day: per-speaker loudness normalisation to the real game VO (`docs/research/loudness-analysis-2026-10-11.md`),
a staged Wwise Opus tone test for compression (`tools/bnk_patch/opus_wem.py`, `tone_test3.py`, not yet heard in game), and a
test render of mixed speech-plus-narration cues (`tools/render_corpus/mixed.py`, `mixed_render.py`).
