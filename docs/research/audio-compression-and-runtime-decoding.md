# Compressing the rendered dialogue and decoding it at runtime

Research notes, 2026-10-12. Written so a later session can pick this up without redoing the investigation. Nothing here has been
tested in the game yet unless it says so. Each claim is tagged **confirmed** (seen in the game's files or in our own tests),
**community** (forum posts, not official), or **unverified** (recall or inference).

## 1. The problem

- The installed bank set stores our audio as uncompressed PCM wems (24 kHz mono 16-bit, `WAVE_FORMAT_EXTENSIBLE`).
  Before the 2026-10-12 overnight build it was 12,475 clips in 10.7 GB. After it, 19,889 replaced clips in six bank files, 15 GB.
  The codex/item strings (11,206 more clips, about 20 audio-hours, about 3.5 GB of PCM) are not in the bank for this reason.
- **Confirmed:** the AIVO mod (`W40KRT_AIVOMod`, by pas2k) adds its `soundbanks` folder as a Wwise base path and calls
  `AkSoundEngine.LoadBank` on every `*.bnk` in alphabetical order at startup. So every bank, media included, is resident for the
  whole session. Memory in the game with 15 GB of banks has never been measured (it was about 8.3 GB loaded for the older set).
- Goals: smaller download and disk footprint, and less memory in the game. Both can be met either by a smaller codec inside the
  banks (section 3), or by keeping the audio compressed on disk and decoding each line just before it plays (section 4).

## 2. What the game gives us (all confirmed from the files)

- Engine: Unity **6000.0.64f1**, Mono scripting backend (a `MonoBleedingEdge` folder and ordinary .NET assemblies in
  `WH40KRT_Data/Managed`; no IL2CPP). Unity's own audio is disabled, Wwise is used instead.
- Wwise **2022.1** (the native `Plugins/x86_64/AkSoundEngine.dll` is only 2.9 MB, a trimmed build; its strings point at
  `wwise_v2022.1`). Its strings include `OpusHead` and `OpusTags`, which hints at Opus handling in the engine but proves nothing about
  playback.
- The managed wrapper `AK.Wwise.Unity.API.dll` (decompiled with `ilspycmd`) has, among others:
  - `AKRESULT SetMedia(AkSourceSettingsArray in_pSourceSettings, uint in_uNumSourceSettings)`
  - `AKRESULT UnsetMedia(AkSourceSettingsArray, uint)`
  - `AKRESULT LoadBankMemoryView(IntPtr ptr, uint size, out uint bankID)` and `LoadBankMemoryCopy(...)` with the same shape
  - `AkSourceSettings { sourceID, pMediaMemory, uMediaSize }`, and `AkExternalSourceInfo` (external sources)
  - `const int AK_BANK_PLATFORM_DATA_ALIGNMENT = 16`
  - `AKRESULT.AK_BankAlreadyLoaded = 69` (the enum is in the same assembly if a later session wants the other result codes)
- The native DLL exports the matching `CSharp_SetMedia`, `CSharp_LoadBankMemoryView/Copy`, `CSharp_AkSourceSettings_*`.
- Existing mods in this project, including the AIVO mod, build as **net48/net481** class libraries and load fine under UnityModManager
  with Harmony 2.x. The AIVO mod already patches `AkSoundEngine.PostEvent(string, GameObject)` with a Harmony prefix and has an
  `OnUpdate` hook (UMM calls it every frame).
- The `Managed` folder contains `netstandard.dll`, `System.Memory.dll`, `System.Runtime.CompilerServices.Unsafe.dll`, Newtonsoft.Json,
  MemoryPack and `0Harmony.dll`. It contains **no** Ogg, Opus, MP3, FLAC or NAudio library.
- Banks that already play in the game: PCM wems with the extensible header (proved 2026-10-11, see
  `docs/research/silent-replaced-audio-brief.md`), and **media-only side banks** (BKHD + DIDX + DATA, no HIRC), which is what the
  `_pcm1..5` files are.

## 3. Option A: a smaller codec inside the banks

### Opus wems
- **Confirmed (ours):** `tools/bnk_patch/opus_wem.py` writes a Wwise Opus wem (fmt tag `0x3041`, per-frame `seek` chunk, raw packets),
  `patch.py --codec opus` uses it with the loudness gain applied before encoding, and `vgmstream-cli` decodes our output.
  Size is about 13x smaller than PCM: 12,475 clips would be about 0.9 GB instead of 10.7 GB, so the current 19,889 clips would be
  roughly 1.3 GB, and no side banks would be needed.
- **Unverified (the blocker):** that the game's Wwise plays it. The plugin ids written into the bank (`0x00140001` AKOPUS_WEM, and
  `0x00130001` AKOPUS as the alternative) are best guesses, `(codecId << 16) | 1` with PCM = 1, Vorbis = 4, AKOPUS = 19,
  AKOPUS_WEM = 20. They must be checked against `AkTypes.h` of a 2022.1 SDK. The Opus plugin may also simply not be in this game's
  trimmed engine. Nothing in the web research settled this (the Audiokinetic docs returned HTTP 403 to the research agent).
- **Test already staged:** `/home/geoff/rt-mods/tone-test3-opus/w40krt_avio_charvogen.bnk` (main bank only). Four Footfall lines: A Opus
  plugin `0x00140001`, B Opus plugin `0x00130001`, C Opus with cbSize 16 and `0x00140001`, D PCM control. Lines to listen for:
  "While you are engaged in small talk", "It's strange - a small-time hustler", "Behind the carefully built facade",
  "You have heard of periods of warp instabil". If any Opus line plays, switch `patch.py` to `--codec opus` and re-verify loudness.
  Procedure: swap only the main bank in, play the lines, restore the previous set (the installed set must be moved aside, not deleted).

### Other in-bank codecs
- **Wwise Vorbis** (the game's native codec, plugin 4): producing it needs Wwise's authoring tool; no open encoder is known. Not an option.
- **Wwise ADPCM** (core codec): roughly 4:1, so about 15 GB to about 4 GB. Always present in the engine in principle, but the wem
  header layout is **unverified** and no writer exists. It would need its own tone test. Quality is lower (4 bits per sample).

## 4. Option B: keep clips compressed on disk, decode just before playback

Idea: store each clip as a small compressed file, and have the mod decode it to PCM on a background thread when a line is about to
play, then hand the PCM to Wwise. Banks would hold only event/sound structure (tiny), and memory is used only for lines in flight.
It also makes re-rendering a file swap with no bank rebuild.

### Two ways to give Wwise the audio
1. **`SetMedia` (media replacement).** Ship banks with the media stripped, then per line: decode, allocate a native buffer, build an
   `AkSourceSettings` array with the media's source ID, call `SetMedia`, `PostEvent`, and `UnsetMedia` when the voice is finished.
   - **Unverified (recall, not from docs):** it applies to sources whose structure is already in a loaded bank but whose media is not
     in any loaded bank; the source must be an in-memory source rather than streamed; if the media is already in a loaded bank the call
     likely fails (an `AK_MediaAlreadyLoaded`-style error); the memory must stay valid, aligned to 16, until the unset succeeds and no
     voice uses it; `TryUnsetMedia` is the non-forcing variant and fails while a voice still plays the media.
   - **Community:** an Audiokinetic answer says events in auto-defined (no-media) banks need their media loaded after `LoadBank`,
     either with `PrepareEvent` or with `SetMedia`.
2. **A small media-only bank loaded from memory.** Build BKHD + DIDX + DATA in memory from the decoded PCM, call
   `LoadBankMemoryView` (buffer aligned to 16, pointer stored by the engine, memory must stay valid until `UnloadBank`), play, then
   unload and free. This reuses what is already proven (media-only banks play) and avoids the `SetMedia` rules.
   - **Community, version-specific:** one 2019.2.0 report says `UnloadBank` did not free "Total Reserved Memory" allocated by `LoadBank`.
     That is old; test it on this build before relying on the memory saving.
   - **Community:** loading a bank through the memory overload can change later loose-media lookups (a `PrepareEvent` then asked for
     `.bnk` files instead of `.wem`). Be ready for lookup quirks.
- External sources (`AkExternalSourceInfo`) are the weakest option: the event must be authored with an External Source slot, and the
  AIVO events are not.

### Threading and memory (mostly community or inference)
- Treat every Wwise call as **main-thread only**. Community posts show `PostEvent` from a worker thread touching unsynchronised
  `RegisteredGameObjects` state and Unity APIs, and the wrapper enforces main-thread use in at least one place. Design: a worker
  thread decodes and fills a `ConcurrentQueue`; the mod drains it from UMM's `OnUpdate` and makes all `AkSoundEngine` calls there.
- Wwise keeps the pointer it is given, so use `Marshal.AllocHGlobal` (or `NativeMemory`), aligned to 16, not a pinned managed array.
  Free it only after `UnsetMedia`/`UnloadBank` has completed and the voice has ended. Unity uses the Boehm GC (non-moving,
  incremental mode on by default, per the Unity manual), but long-lived pinned handles are discouraged.
- Harmony: the `AkSoundEngine.PostEvent` overloads are ordinary static C# methods over the SWIG `P/Invoke` layer, so prefix/postfix
  patches work (the AIVO mod already does this); pin each overload by parameter types. Patching the `P/Invoke` externs is fragile.
- Unity 6 offers the `.NET Standard 2.1` (default) and `.NET Framework` (4.8 plus the 2.1 APIs) compatibility levels. Plug-ins built for
  .NET Framework are only fully supported on the Framework profile. Our net48 mods work in this game, so check
  `System.Memory`/`System.Buffers` resolve before leaning on `Span<T>`.

### Decoders (research agent, package pages and READMEs only; licenses not read from the LICENSE files)
| Format | Library | Notes |
|---|---|---|
| Opus (recommended) | `Concentus` 2.2.2 + `Concentus.OggFile` 1.0.7 | pure C#, netstandard2.0/net452; needs `System.Memory` and `System.Numerics.Vectors`; OggFile is MIT; core license not read (port of libopus, expect BSD-style, verify). Author claims 40 to 50% of native libopus speed. |
| Ogg Vorbis (fallback) | `NVorbis` 0.10.5 | MIT per its README; netstandard2.0/net45; needs `System.Memory`, `System.ValueTuple`. About 2.8M downloads. A 1.0 rewrite is in release-candidate. |
| MP3 | `NLayer` 3.0.0 | MIT, no dependencies, but 24 kHz mono needs MPEG-2 LSF and has poor quality per byte; MP3 also adds start/end padding that complicates gapless timing. Not recommended. |
| FLAC (lossless) | `CUETools.Codecs.FLAKE-Reloaded` 1.0.1 or `Shamisen.Codecs.Flac` (alpha) | only if lossless is needed; 5 to 8x larger than Opus; license of the first is unverified. |
| ADPCM | hand-written | about 100 lines; poor quality at this rate. |
- NAudio is not needed (its useful codecs are Windows ACM/MediaFoundation wrappers, unusable here).
- **Format choice:** Opus at 16 to 24 kbps, 24 kHz mono (a native Opus rate, no resampling). Needs pre-skip handled so clips do not start
  with silence. Decode estimate: well under 10 ms for a 10 s clip, **unmeasured on this runtime**.
- **Shipping:** decoder DLLs next to the mod with an `AppDomain.AssemblyResolve` handler, or merged with ILRepack. Do not ship a second
  `System.Memory`; the game already has one.

## 5. The one experiment that settles it

Needs one game session and a small mod change. No GPU.
1. Build a variant bank where one voiced line's media is removed but its event/sound structure (HIRC) stays.
2. In the mod, create an aligned native buffer holding a short tone as an extensible-PCM wem, build an `AkSourceSettingsArray` with that
   source ID, call `AkSoundEngine.SetMedia`, log the `AKRESULT`, post the event, and listen.
3. Repeat with the media left in the bank, to see whether `SetMedia` overrides it or errors (and with which code).
4. Call `TryUnsetMedia` while the voice plays and again after it ends; log both results.
5. If `SetMedia` fails, try the media-only-bank route with `LoadBankMemoryView`, then `UnloadBank`, and watch process memory.
6. In the same session, play the Opus tone-test lines (section 3). One session answers both questions.

## 6. Decision guide
- Opus lines play in the tone test: use `patch.py --codec opus` (smallest change, about 1.3 GB, no mod code). Re-verify loudness.
- Opus does not play but `SetMedia` works: runtime decoding of Opus/Vorbis in the mod. More work, least memory, easiest re-renders.
- Neither: media-only bank loaded from memory, or ADPCM after its own tone test, or ship PCM and limit the set (leave out the
  codex strings, about 3.5 GB).

## 7. Where things are in the repo
- Opus writer and PCM writer: `tools/bnk_patch/{opus_wem.py,wem.py,patch.py,bank.py}`; tone tests `tone_test*.py`.
- Build chain: `tools/render_corpus/night_build.py` (stitch, export, patch, verify); install notes in `HANDOFF-2026-10-11-overnight.md`.
- Silent-audio bug and the extensible PCM header: `docs/research/silent-replaced-audio-brief.md`; loudness: `docs/research/loudness-analysis-2026-10-11.md`.
- Mod entry points to extend: the AIVO mod (decompiled copy was at the session scratchpad; regenerate with
  `ilspycmd -p -o <dir> .../UnityModManager/W40KRT_AIVOMod/W40KRT_AIVOMod.dll`) and our Dialogue Flag mod in `tools/dialogue_flag/`
  (it already hooks `VoiceOverPlayer.PlayVoiceOver`, which could trigger the prefetch).
- Regenerate the Wwise wrapper source with `ilspycmd` on `WH40KRT_Data/Managed/AK.Wwise.Unity.API.dll`.

## 8. Caveats on the research
- The Audiokinetic documentation and Q&A pages returned HTTP 403 to the research agent, so all Wwise API semantics above marked
  unverified are recall plus forum snippets. The headers of a Wwise 2022.1 SDK (`AkSoundEngine.h`) would settle most of them.
- The decoder agent read NuGet pages and READMEs only. Read the LICENSE files before shipping anything.
- Wwise calls from non-main threads: no authoritative statement found; the design above avoids the question.

## Sources
- Unity 6 .NET profile support: https://docs.unity.cn/Manual/dotnet-profile-support.html
- Unity garbage collection: https://docs.unity3d.com/Manual/dotnet-garbage-collection.html
- Klei modding thread on Unity 6 and net48: https://forums.kleientertainment.com/forums/topic/170067-modders-now-face-a-dilemma-with-unity-6/
- Audiokinetic Q&A, media for auto-defined banks: https://audiokinetic.com/qa/1893/prepareevent-fails-to-load-media?show=1897
- Audiokinetic Q&A, `LoadBankMemoryView` and `PrepareEvent`: https://audiokinetic.com/qa/8976/prepareevent-fails-for-bank-loaded-with-bankloadmemoryview
- Audiokinetic Q&A, calling sound engine functions off the main thread: https://www.audiokinetic.com/qa/14209/calling-soundengine-functions-from-global-callbacks
- Audiokinetic Q&A, `RegisteredGameObjects` HashSet error: https://www.audiokinetic.com/qa/11706/hashset-indexoutofrangeexception-when-registering-object
- NVorbis: https://www.nuget.org/packages/NVorbis ; Concentus: https://www.nuget.org/packages/Concentus ; Concentus.OggFile: https://www.nuget.org/packages/Concentus.OggFile ; NLayer: https://www.nuget.org/packages/NLayer
