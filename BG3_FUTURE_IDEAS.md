# BG3 Neural Speech Mod - Future Idea Dump

Not started. Written up after finishing the Rogue Trader mod's research phase, while the
architecture and its open questions were still fresh, so a future session (or a fresh one) can
pick this up without redoing the research. Assumes the RT mod's tooling (TtsSidecar, annotation
harness, bake-off/listening-test scoring, prompt-bank builder) is done and reusable as a
starting point.

## Why BG3 is a different shape of problem than RT

RT is ~90% unvoiced (companions, NPCs, narration - almost everything). BG3 is the opposite:
Larian fully voiced every NPC/companion line, and even fully voiced *custom Tav's own dialogue
choices was planned and cut* after fan feedback during development - too many branching paths to
voice for every preset. So in BG3, "unvoiced" isn't a scattered gap, it's specifically:
- **The player's own dialogue choices** (custom Tav and Dark Urge) - effectively the whole
  player-side of every conversation tree, not just a handful of lines. This is the main target,
  and it's a *voice-matching* problem (make new lines sound like the preset voice you already
  picked) more than a "give silent NPCs a personality" problem like RT.
- Narrator/descriptive text (item examine, some cutscene narration) - smaller, already has partial
  community solutions (Nimi Narrator and a few AI narrator voice-swaps exist).
- Any new content added by *other* BG3 mods (custom companions, dialogue-rewrite mods like GPT-4
  Tav backstory mods) - text with no VO at all, same shape of problem as RT.

Premade Origin companions if played directly: mostly a non-problem, they're voiced already.

## Architecture mapping (RT piece -> BG3 equivalent)

| RT piece | BG3 status |
|---|---|
| `TtsSidecar` (Python/GPU server) | Reusable as-is, game-agnostic. |
| `tools/tts_bakeoff`, `annotate/`, `audio_match/`, `listening_test/` | Reusable as-is - new corpus, new gold set, same code. |
| `unpack_pck.py` / vgmstream | Same *technique*, different container: BG3 audio is Wwise `.wem`/`.pck`/`.bnk` same as RT, but reached via LSLib instead of whatever unpacked RT's `.pck`s. vgmstream itself is already credited/vendored - stays the same tool either way. |
| `build_prompt_banks.py` | Reusable technique. New target: reference clips of the *player's own selected preset voice* (Voice 1-8ish, both genders), not just companions. |
| `DialogueExporter` (UMM, live blueprint dump) | No direct equivalent found. BG3's dialogue lives in `.lsf`/`.lsj` timeline files (`Public/Gustav(Dev)/Timeline/Generated`), parseable **offline** via LSLib - no need to hook a running game the way RT's exporter does. Closest existing prior art: `bg3-dialog-reader` (tree-structured SQLite/HTML export, but speaker-name resolution needs a manual DOS2-editor-folder step per its README - unverified how well that holds up at full-corpus scale). |
| `extract_localization.py` (strings + voiced map) | Needs a BG3-specific rewrite against `.loca`/`.xml` handle-keyed strings (LSLib converts loca<->xml). "Voiced or not" cross-reference: **NoComply's BG3 Dialogue Finder (BG3DF)**, 291k-row CSV of character/text/filename/audio-type, is the closest existing thing to RT's `Sound.json` check. |
| Runtime mod (C#/Harmony/UMM) | Becomes a **bg3se Lua mod**. BG3 isn't Unity/IL2CPP - there's no Harmony-style reflection hooking available; you're entirely dependent on whatever bg3se (Norbyte's Script Extender) already exposes. Rich Osiris event surface exists (`Osi.Events.lua` in LaughingLeader's BG3ModdingTools) since Osiris has driven Larian's dialogue/quest logic since DOS2 - a dialogue-node/line event almost certainly exists, but **the exact event name is unverified** - this is the single biggest open risk, same role RT's "is Unity audio actually disabled" spike played. |
| HTTP call to sidecar | **Blocked.** Confirmed via bg3se issue #479: no `socket.http`, no raw sockets from Lua. Workaround: file-based polling IPC (`Ext.IO.SaveFile`/`LoadFile` are real, documented) - write a request file, sidecar watches the dir and writes a WAV + sentinel, Lua polls and plays it. Same pattern RT's own `speech_test.request` control-file self-test already uses, just promoted from test-only to the real IPC mechanism. Latency matters more here than it did for RT's HTTP call - lookahead/prefetch is probably *more* load-bearing for BG3, not less. |
| Audio playback bypass (`NativeAudioPlayer`, MCI/paplay) | Directly portable concept. BG3 is also Wwise-based; playing WAVs straight to the OS device, bypassing the game's own audio engine entirely, should work the same way it did for RT. Unverified whether BG3's Wwise setup causes any different interaction (e.g. ducking/mixing conflicts) than RT's already-disabled Unity audio manager. |
| "Voiced lines never re-synthesized" | Needs BG3's version of the voiced/unvoiced check - ties back to the localization/voiced-map export line above. |

## .pak / resource format: already solved, not a reverse-engineering task

**LSLib** (Norbyte - same author as Script Extender - MIT licensed,
https://github.com/Norbyte/lslib) fully handles: PAK (LSPK) extraction/creation, LSV savegames,
LSF/LSX/LSJ/LSB resource conversion (includes the dialogue timeline files), and Osiris story
database editing. Ships as a real scriptable CLI (`Divine.exe`, plus a maintained fork at
fireundubh/divine) - not GUI-only, so it's automatable. It does **not** touch Wwise audio itself
(`.wem`/`.pck`/`.bnk`) - that's a separate, already-solved stage via vgmstream/wwiser, same as RT.
Open question not yet answered: whether LSLib has a Python binding or needs to be shelled out to
as a subprocess from the (Python-heavy) tools/ scripts - check before assuming either way.

## Bark/voice-cloning source material

- **Origin companions**: solved and published. "Voice Swaps" / "Voice Swaps 2" mods on Nexus
  document "100% of character voice lines isolated using deterministic approaches" per companion -
  proof this is a solved extraction problem, same category as RT's `extract_voice_lines.py`.
- **Custom Tav preset voices (the actual target)**: partially solved, not cleanly. Leads to
  chase, none fully verified:
  - Nexus mod "All Voice Sound Effects Isolated By Character (Player and Companion)"
    (nexusmods.com/baldursgate3/mods/16479) - title implies exactly what's needed, but Nexus
    blocks WebFetch (403) so scope/completeness is unconfirmed - open the page directly.
  - `bg3-ai-voicetoolkit` (github.com/StableFluffy/bg3-ai-voicetoolkit) - RVC-based (voice
    conversion of existing audio, not zero-shot TTS cloning like Chatterbox/Qwen3), has a
    "Select Character" step implying a maintained character/voice list, contents unverified
    (README is minimal, GitHub page fetch didn't surface it).
  - The generally-described community workflow is semi-manual: find a voice ID handle, search it
    in BG3 Modders Multitool, cross-reference the Soundbanks file to identify which `.wem`s belong
    to it. Automatable in principle, not automated by anyone found yet.
- **Structural wrinkle RT didn't have**: bark/dialogue audio is split across two separate paks -
  `Voice.pak` (story dialogue, cutscene barks, point-and-click lines) and `SharedSounds.pak`
  (combat barks, character vocalizations). A complete reference bank for any voice needs both.

## Dialogue export for the annotation pipeline

No single tool matches `DialogueExporter` + `build_conversations.py` exactly; combine:
- **`bg3-dialog-reader`** (github.com/angaityel/bg3-dialog-reader) - tree-structured export
  (not flat), SQLite DB with tags/flags/translation, HTML export, audio export via vgmstream.
  Closest thing to a real conversation-graph exporter. Speaker-name resolution needs a manual
  `_merged.lsf`-in-DOS2-editor-folder step per its README - verify this holds at full scale.
- **NoComply's BG3DF** - flat 291k-row CSV (char/text/filename/audio-type) - best source for the
  voiced/unvoiced cross-reference, not for tree structure.
- **Community "datamined dialogue" parser** (shared via Tumblr/roksik-dnd, parser on GitHub,
  re-runnable against current patch) - richest context per line: tags, approval values, roll
  requirements, dev notes. Potentially better annotation-context fuel than RT's
  `character_bios.json`, since it's per-line rather than per-speaker.
- **"BG3 Point-Click Dialogue Files Database"** (Nexus mod 9566) - compiles all point-and-click
  (ambient bark) dialogue for all player characters specifically - the other unvoiced-for-Tav pool
  besides conversation-tree choices.
- None of these confirmed to cleanly separate player-choice lines from NPC lines in their output
  schema, or confirmed current against the latest patch - verify before trusting at corpus scale.
- Fallback if all of the above fall short: parse `.lsf`/`.lsj` timeline files directly via LSLib -
  pure offline static parse, arguably simpler than RT's live-game-hook exporter since it doesn't
  need the game running at all.

## Legal flag - check before committing to this project

Search turned up a claim that **Larian's fan-content policy prohibits using their work to train
AI models** - this was not verified against Larian's actual current policy text, just a search
snippet. RT's project has no equivalent restriction (the opt-in-local-cloning-only rule there is
a self-imposed ethics choice, not a licensing requirement). If BG3's policy is actually stricter,
it could block the voice-cloning approach entirely regardless of the "never distribute cloned
voices, build locally from the user's own files" mitigation that satisfies the RT project's own
ethics bar. **Read Larian's actual current fan-content/community guidelines before starting.**

## Suggested first steps when this gets picked up

1. Re-verify everything above against whatever's current at that time - patches, tool updates,
   and Larian's policy could all have moved.
2. Confirm the bg3se dialogue-line event actually exists and fires with the right data
   (text, speaker, cue identity) - this is the load-bearing spike, same role as RT's Unity-audio
   check. If it doesn't exist cleanly, the whole runtime side needs a different approach.
3. Confirm file-polling IPC latency is acceptable with prefetch/lookahead - the RT project's HTTP
   call assumption doesn't carry over, this needs its own measurement.
4. Try `bg3-dialog-reader`'s SQLite output against a small conversation and check whether
   player-choice lines are structurally distinguishable from NPC lines in it.
5. Actually open the Nexus "isolated by character (Player and Companion)" mod page and confirm
   whether it already covers all Tav voice presets before spending time re-deriving that.
