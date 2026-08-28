# Reading Rogue Trader's Text Aloud with Local TTS: What Already Exists

## TL;DR
- A mature, MIT-licensed, open-source foundation already exists: **Osmodium's "W40K SpeechMod"** (live Windows SAPI/macOS `say` narration of virtually all unvoiced text) and **pas2k's "W40K – AI Voiceover" mod**, which is a fork of SpeechMod that swaps live SAPI for pre-rendered neural voices (Chatterbox TTS) packaged as Wwise `.bnk` soundbanks. You do not need to build the text-capture layer from scratch — you should fork SpeechMod.
- The hard, reusable work is already solved and documented: SpeechMod hooks Owlcat's Unity MVVM **view classes** (e.g. `SurfaceDialogCueView`, `BookEventCueView`/`BookEventPCView`, `DialogAnswerPCView`, `SubtitleView`, `ExplorationSpaceEventPCView`) via Harmony under the game's built-in UnityModManager, and the same author maintains sibling mods for Pathfinder: Kingmaker and Wrath of the Righteous, so the hook code is proven to port.
- The genuine gap for your goal is the **runtime local open-source model integration**: no existing Rogue Trader mod streams from a local open-source TTS server (Piper/Kokoro/XTTS/F5/AllTalk) at runtime. SpeechMod uses OS SAPI; AIVOMod pre-renders offline and ships static `.bnk` files. Wiring a localhost TTS server into SpeechMod's existing capture hooks is the net-new component you would write.

## Key Findings

### 1. Rogue Trader has no built-in screen-reader / OS narration
Owlcat has confirmed there is **no full voiceover planned** for Rogue Trader. In its official AMA (owlcat.games/news/92) the studio stated: "Yes, we plan to move forward with full VO for the next projects... As for Rogue Trader, the Lord Captain's voidship has unfortunately also already sailed, so currently there's no plan to update it with full VO." An Owlcat developer ("Starrok") reiterated on Steam (1 Apr 2024): "Unfortunately that's way beyond the scope of our budget. We've added some VO in one of the first patches, but that's mostly it, except for additions in the DLCs." The studio's accessibility work to date has centered on colorblind mode, not text-to-speech or screen-reader output. There is no built-in SAPI/NVDA/JAWS/Narrator/speech-dispatcher integration. All narration capability is community-mod-supplied.

### 2. The core mods exist and are actively maintained
- **W40K SpeechMod** (Osmodium/"Oozed") — Nexus mod 75 (`nexusmods.com/warhammer40kroguetrader/mods/75`), GitHub `Osmodium/W40KRogueTraderSpeechMod`. Latest **v1.2.0, released 24 October 2025**. MIT license. 333 endorsements as of this research. Actively maintained (13 releases; first released 24 Dec 2023). Live TTS, no pre-baked audio.
- **W40K – AI Voiceover mod** (pas2k) — Nexus mod 431 (`nexusmods.com/warhammer40kroguetrader/mods/431`), GitHub `pas2k/W40KRT_AIVOMod`. Fork of SpeechMod. MIT license. Uses pre-rendered Chatterbox TTS voices shipped as Wwise `.bnk` soundbanks; voice packs downloaded separately. Per pas2k's page: the recommended "Common Voice-derived voicepack" (Nexus 429) uses "Charvogen and my own voice... No OwlCat games used for voice cloning" (licensed CC-BY-SA 4.0), while the "(Outdated) Voice-cloned characters" pack (Nexus 430) has "No Infinite Museion, no fast forward, limited roster... Might have conflict of interests with voice actors, so might be taken down."
- **W40KRogueTraderElevenLabsMod** (loopinkk) — GitHub fork of SpeechMod, version 0.9.9, marked "UNDER DEVELOPMENT," no releases, appears experimental/abandoned.
- **40k Dark Heresy TTS mod** (Nexus, Dark Heresy game) — another SpeechMod port, updated for the May 2026 Dark Heresy beta, showing the codebase is being actively carried forward to newer Owlcat titles.

### 3. Reusable hook knowledge is well-documented
SpeechMod's `Todo.txt` is effectively a map of Owlcat's dialogue/UI system, listing the exact view classes and scene-graph transform paths for every text surface. Owlcat also publishes official modding templates and the game bundles UnityModManager + Harmony.

### 4. Prior art in other games confirms both architectures
- **Pillars of Eternity** — VaultDoc's "VaultVox"/POESpeechMod (Nexus 425): the author states it "reads most (~94%) of the game's unvoiced text aloud in real time (dialogue, journal, tooltips, UI, etc.)... Originally built for accessibility (dyslexia)." It auto-skips voiced lines and uses Windows SAPI + optional NaturalVoiceSAPIAdapter. The closest analog to your goal.
- **Disco Elysium** — `sychotixdev/DiscoElysiumReader`: an injected mod that writes captured dialogue to a text file, read by a **separate external program** (out-of-process architecture, because the game didn't load System.Speech). Directly relevant to your "external local server" question.
- **Skyrim/Fallout Mantella** — external Python pipeline (Whisper + LLM + Piper/xVASynth/XTTS) — proof of the localhost-server pattern.

### 5. Practical gotchas are documented by users
Double-narration of voiced lines, barks overlapping, headphone/audio-device routing bugs, version breakage after DLC, and multiplayer desync are all reported.

### 6. Gaps
No runtime local-open-source-model narration exists for Rogue Trader; no Linux/Proton support in SpeechMod; no in-process neural inference.

## Details

### Screen-reader / OS-level narration (Q1)
Rogue Trader ships **no** screen reader, TTS accessibility option, or pipe to SAPI/NVDA/JAWS/Narrator/speech-dispatcher. Owlcat stated in its community AMA that full VO is not coming to Rogue Trader and that colorblind mode was their first accessibility feature. The only OS-level narration is via SpeechMod, which calls Windows SAPI through a bundled native `WindowsVoice` C++ helper (and macOS `say`). Users improve voice quality by installing the third-party **NaturalVoiceSAPIAdapter** to expose neural/offline Windows voices to SAPI.

For the earlier Unity titles, the same author maintains **`Osmodium/PathfinderTextToSpeechMod`** (WotR, Nexus 241) and **`Osmodium/KingmakerSpeechMod`** — confirming the hook approach ports across Kingmaker → WotR → Rogue Trader → Dark Heresy. pas2k likewise ships a WotR AI Voiceover (`pas2k/WotR_AIVO`, Nexus 1028). This is strong evidence your effort should target the shared SpeechMod codebase rather than a single game.

### Existing AI voiceover mods and how they hook the dialogue system (Q2)
**W40K SpeechMod** (MIT, live generation): Runs as a UnityModManager mod using the Harmony that ships inside Rogue Trader. It does not read `BlueprintCue` data directly; instead it patches Owlcat's MVVM **view** layer — the classes that render text to the screen — and reads the `TextMeshPro`/`Text` component contents. From the repo's own `Todo.txt`, the targeted view classes and objects include:
- `SurfaceDialogCueView` (main dialogue cue text)
- `DialogAnswerPCView` (player response options)
- `BookEventCueView` / `BookEventPCView` (book events + historical text)
- `SubtitleView` (cutscene subtitles — flagged as a possible double-playback source)
- `ExplorationSpaceEventPCView` / `DialogCuePCView` (space events)
- `CharacterInfoPCView`/`CharInfoStoriesView` (biography), `EncyclopediaPageBaseView` (Corpus Valancius), `JournalQuestPCView`, `ShipPostsView`, `ShipNameAndPortraitPCView` (via `BindViewImplementation`), `LoadingScreenPCView`, `TutorialPCView`, `MessageBoxPCView`, `WelcomeWindowPCView`, `OvertipMapObjectInteractionPCView` (barks/banter).

Speaker/gender: the mod supports "gender-specific voices," a "protagonist-specific voice," and per-gender bark voices, so it resolves speaker identity, but I could not confirm from source whether gender is read from a cue blueprint, the entity, or the view model. **This is the one detail to verify by reading the patch `.cs` directly before you rely on it.** TTS is generated live at runtime (README: "This mod contains no AI and no pre-baked voice files!").

**W40K – AI Voiceover** (MIT, pre-rendered): A SpeechMod fork that keeps the same capture hooks but, instead of live SAPI, plays **pre-rendered neural audio**. Voices are generated offline with **Chatterbox TTS** (the "Charvogen" custom pack additionally uses PyTorch + AudioLDM2), then packaged into **Wwise `.bnk` soundbanks** built with the `wwiser` parser, dropped into `W40KRT_AIVOMod\soundbanks`. It adds spatial mixing and a `]` fast-forward key. The repo's own known-issues list is highly instructive for your design: "Due to difficulty of statically resolving dialogues, some voices might be wrong," and "Since SoundBanksInfo.xml is not available for RT, the topology used is 'Whatever works.'" The `JsonPreproc` folder handles cue-to-audio mapping. I could not confirm verbatim that it calls `AkSoundEngine.PostEvent`, but the architecture (cue identity → Wwise event in a `.bnk`) is clear from the README and folder layout. **Because it pre-renders, it cannot voice text that wasn't processed offline (new DLC lines lag); the "Voice-cloned" pack is explicitly outdated and lacks Infinite Museion/DLC content.**

### Reusable hook knowledge (Q3)
- **Game integration**: Rogue Trader has "deep integration with UMM" — UnityModManager and Harmony are **built into the game**; you just drop a mod folder into `%userprofile%\AppData\LocalLow\Owlcat Games\Warhammer 40000 Rogue Trader\UnityModManager\` and press Ctrl+F10. The game uses **Harmony v2.2.2.0**.
- **Templates/tooling**: Owlcat publishes `OwlcatOpenSource/RTModificationTemplate` and the WrathModificationTemplate; ADDB's NuGet templates (`xADDBx/OwlcatNuGetTemplates`, `Owlcat.Templates` on NuGet) provide `rtmod`, `rtbpmod`, etc. project scaffolds, some with automatic Wwise soundbank loading — notably, "If the event name matches an answer/cue/dialog GUID, the sound event should automatically play when that answer/cue/dialog is displayed," which is exactly the cue→audio hook the AIVO mod relies on.
- **Community wiki**: `WittleWolfie/OwlcatModdingWiki` (and `spacehamster` fork) documents the blueprint system, decompiling with dnSpy/ILSpy/dotPeek, and Harmony patching. **ModFinder** (Nexus 146) and **BubblePrints** are the standard discovery/inspection tools.
- **Workflow**: decompile `Assembly-CSharp.dll` with dnSpy → write a Harmony patch → load via UMM.

### Prior art in other games (Q4)
- **Pillars of Eternity — VaultVox / POESpeechMod** (VaultDoc, Nexus 425): reads ~94% of unvoiced text in real time; auto-skips voiced lines; per-NPC varied voices; 22 languages; word-by-word highlight; hands-free auto-advance; skip hotkey (v1.2.0f1). Uses **Windows SAPI** (built-in), optional NaturalVoiceSAPIAdapter for neural voices. In-process, OS-TTS architecture — the model your project most resembles, minus the local open-source engine.
- **Disco Elysium — DiscoElysiumReader** (sychotixdev, GitHub): injected `.dll` writes current dialogue (ActorName, Conversant, text) to `WriteText.txt`; a **separate external `.exe`** reads the file and speaks it (had to be out-of-process because the game didn't load `System.Speech`). This is a working template for the **external-local-server** pattern you're considering.
- **Skyrim/Fallout — Mantella**: external Python 3.11 pipeline calling Piper/xVASynth/XTTS — canonical proof of a localhost TTS server driving a game.
- **Baldur's Gate 3 / Wasteland 3**: only pre-baked AI voice-replacement packs or RVC models exist; no live unvoiced-text narration mod was found. BG3 has no live-TTS dialogue-reader; some AI narrator packs were pulled after VA legal complaints.

### Practical gotchas people report (Q5)
- **Double-narration**: SpeechMod's own `Todo.txt` flags `SubtitleView` as risky — "might use barks, so might incur some double playback sometimes." An "Auto play ignores voiced dialog lines" setting exists specifically to avoid narrating already-voiced lines; users must also turn off the base dialog reading when using it.
- **Bark overlap**: AIVOMod notes "Barks sometimes overlap and are poorly attenuated by the camera position"; SpeechMod exposes "Only playback barks if silence" and separate toggles for vicinity/cutscene-triggered barks to mitigate flooding.
- **Text advancing before audio finishes**: managed via "Interrupt speech on play" (interrupt vs. queue) and, in the Pillars analog, hands-free auto-advance timed to speech end — a pattern you'd replicate.
- **Audio device routing**: users report the mod voice stays on speakers while game audio moves to headphones (SAPI uses the default device, not the game's).
- **Version breakage**: multiple Steam posts report SpeechMod deactivating itself or losing its settings button after DLC/patch updates; a folder-name bug (`W40KSpeechMod` vs `W40KRTSpeechMod`) broke the phonetic dictionary path. Confirm compatibility against the current patch (game reached DLCs Void Shadows 24 Sep 2024 and Lex Imperialis 24 Jun 2025; Switch 2 port 11 Dec 2025).
- **Co-op/multiplayer**: Rogue Trader co-op is desync-prone even unmodded; non-host players share only cosmetic content and must match paid DLC. No evidence anyone runs SpeechMod/AIVO in co-op; treat multiplayer as unsupported/untested for a narration mod.
- **Proton/Linux**: SpeechMod's README explicitly lists **Linux: ⛔ Not supported (this includes Steam Deck)** — because it depends on the Windows SAPI native helper. UMM/Harmony themselves work under Proton (the game bundles them), and mods like ToyBox run on Linux via the Proton prefix path (`.../steamapps/compatdata/2186680/pfx/...`), but the TTS backend is the blocker. A local-server design that runs the TTS engine as a native Linux process (or a Proton-side HTTP call to a Linux-native Piper/Kokoro server) would be the way to get Linux/Deck support that SpeechMod lacks.

## Recommendations

**Stage 1 — Fork, don't rebuild.** Fork `Osmodium/W40KRogueTraderSpeechMod` (MIT permits this). You inherit the entire, battle-tested text-capture layer (dialogue cues, answers, barks, books, journal, tooltips, loading screens), the UMM/Harmony scaffolding, the phonetic dictionary, and the gender/voice-selection UI. Study `pas2k/W40KRT_AIVOMod` in parallel as a worked example of replacing the audio backend while keeping the hooks.

**Stage 2 — Replace the audio backend with a localhost TTS server.** Keep SpeechMod's capture hooks; at the point where it currently calls the `WindowsVoice` SAPI helper, instead POST the captured cue text (plus speaker/gender) to a local HTTP server running an open-source model. **Piper** or **Kokoro** are the pragmatic first choices for latency (fast CPU/GPU inference, streaming-friendly); XTTS/F5-TTS/AllTalk if you want voice cloning at the cost of latency. Adopt the DiscoElysiumReader out-of-process pattern to avoid loading heavy ML runtimes inside Mono/Unity.

**Stage 3 — Solve latency and advance-timing.** Stream audio as it's synthesized; start playback on first chunk. Reuse SpeechMod's "interrupt vs. queue" and the Pillars-style "auto-advance after speech ends" logic so text doesn't skip ahead. Cache synthesized clips keyed by cue GUID/text hash so repeated lines are instant (this also gives you a migration path toward the AIVO-style pre-render for stable lines).

**Stage 4 — Avoid double-narration.** Reuse the existing "ignore voiced dialog lines" gate and treat `SubtitleView` carefully. Detect whether Wwise is already playing a VO event for the current cue before synthesizing.

**Stage 5 — Target Linux/Proton as a differentiator.** Because your engine is an external server, run it natively on Linux and have the (Proton-run) mod call `http://localhost`. This delivers Steam Deck support that SpeechMod explicitly does not.

**Benchmarks that change the plan:** If first-audio latency exceeds ~300–500 ms per line with your chosen model, switch to a lighter model (Piper) or pre-render stable cues. If Owlcat ships a game update that renames MVVM view classes (as happened for the Dark Heresy port, which "refactored all Harmony patches to match Owlcat's new MVVM namespaces"), your capture hooks — not your TTS layer — are what will break; keep patches defensive (resolve methods by reflection, fail per-hook not globally).

## Caveats
- I could not extract the **verbatim `[HarmonyPatch(typeof(...))]` attribute strings and Prefix/Postfix method signatures** from SpeechMod's `.cs` files (GitHub's rendered file tree wasn't fetchable in this environment). The view-class targets above come from the repo's `Todo.txt` and README, which are reliable but are not the patch declarations themselves. Read `SpeechMod/` source directly (or clone) before implementation to confirm exact signatures and the gender-resolution source.
- Likewise, AIVOMod's exact cue→Wwise-event mapping (whether it literally calls `AkSoundEngine.PostEvent` with a hashed name) is inferred from its README, folder structure (`JsonPreproc`), and Owlcat template docs — not confirmed from its source.
- Legal/ethical: voice-cloning original actors is contested; the AIVO "Voice-cloned" pack was flagged by its own author as possibly removable over VA conflicts, and BG3 AI-narrator mods were pulled after legal complaints. Prefer non-cloned open voices (as the "Charvogen"/Common Voice-derived pack does).
- Version compatibility is a moving target; SpeechMod v1.2.0 (Oct 2025) is current as of this research, but always check the mod's posts/bug tabs against your installed game build.

### Primary sources located
- W40K SpeechMod: `github.com/Osmodium/W40KRogueTraderSpeechMod` · `nexusmods.com/warhammer40kroguetrader/mods/75`
- SpeechMod Todo.txt (UI hook map): `github.com/Osmodium/W40KRogueTraderSpeechMod/blob/main/Todo.txt`
- W40K AI Voiceover: `github.com/pas2k/W40KRT_AIVOMod` · `nexusmods.com/warhammer40kroguetrader/mods/431` (packs: mods/429, mods/430)
- ElevenLabs fork: `github.com/loopinkk/W40KRogueTraderElevenLabsMod`
- Sibling mods: `github.com/Osmodium/PathfinderTextToSpeechMod` (Nexus WotR 241), `github.com/Osmodium/KingmakerSpeechMod`, `github.com/pas2k/WotR_AIVO` (Nexus WotR 1028); Dark Heresy TTS (Nexus darkheresy/mods/3)
- Owlcat modding: `github.com/OwlcatOpenSource/RTModificationTemplate`, `github.com/xADDBx/OwlcatNuGetTemplates`, `nuget.org/packages/Owlcat.Templates`, `github.com/WittleWolfie/OwlcatModdingWiki`, ModFinder (Nexus 146), Rogue Trader Modding Guide (Steam Workshop discussions)
- Owlcat AMA (no VO): `owlcat.games/news/92`
- Prior art: Pillars VaultVox (`nexusmods.com/pillarsofeternity/mods/425`, ModDB), `github.com/sychotixdev/DiscoElysiumReader`, Mantella (dev.to writeup)