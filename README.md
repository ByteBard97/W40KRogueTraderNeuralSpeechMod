# W40K Rogue Trader - Neural Speech Mod

Live, local, neural text-to-speech for the ~90% of Warhammer 40,000: Rogue Trader that ships
unvoiced. Per-character voices and emotion-annotated delivery are the point; Linux/Proton is
priority #1 here, not a Windows port bolted on afterward.

Nothing here calls out to a cloud API, and nothing ships as pre-rendered audio. The game and the
voice server that actually runs the TTS model are separate processes talking plain HTTP, on
purpose - same PC or a different machine on your LAN, your call, and either OS can be either
role. Details: [Where the TTS engine runs](#where-the-tts-engine-runs).

Status: full corpus is annotated now (count and evidence in
[How the annotations are checked](#how-the-annotations-are-checked)) and audio generates
end to end in automated tests - still running a human listening pass before I'll call that
"done, verified by ear." Right now I'm comparing TTS engines to settle on a recommended default
before cutting a first release - see `PROJECT_PLAN.md` for the full progress log.

## How this differs from other Rogue Trader voice mods

| | This mod | [SpeechMod](https://github.com/Osmodium/W40KRogueTraderSpeechMod) (Osmodium) | [AI Voiceover Mod](https://github.com/pas2k/W40KRT_AIVOMod) (pas2k) |
|---|---|---|---|
| Speech source | Live neural TTS, synthesized on your machine as lines come up | Windows SAPI / macOS `say` | Chatterbox TTS, pre-rendered once by the author and shipped as `.bnk` soundbanks |
| Delivery | Directed per line: 45,114 unvoiced lines are tagged with emotion, pace, and delivery instructions before synthesis (see below) | Flat - adjustable rate/pitch/volume, but no per-line emotional direction | Fixed at render time - the mod's own docs describe "a limited roster of emotions/archetypes" |
| Voice variety | One voice per major companion, with emotion-matched reference clips in progress (see below) | Protagonist / male / female / narrator voices | Two voice packs (a from-scratch "recommended" pack and an older voice-cloned one), both male player character only |
| Player character's voice | Planned: your own dialogue rendered in whatever voice you picked at character creation, toggleable and re-pickable from the mod menu | One fixed "protagonist" voice, not tied to what you actually picked at creation | Fixed male-Rogue-Trader packs only - no player choice, no female protagonist support |
| What's in the download | Code and an annotation file (line IDs → emotion/pace/delivery tags) - no TTS engine, no model weights, no voices, no audio. You bring your own engine (see [Choosing the TTS engine](#choosing-the-tts-engine)) | Code that calls your OS's built-in voice - no audio shipped either | Gigabytes of pre-rendered audio, one `.bnk` soundbank per line |
| Platform | Linux/Proton in progress; Windows ONNX backend designed, not yet built (no date set, but it's a real target, not a maybe) | Windows and macOS only - no Linux/Proton support | Works wherever the game's Wwise banks load (platform-agnostic, since it's pre-baked audio) |
| Cost / licensing | Free, MIT | Free, MIT | Free, MIT |

## Directed delivery, not just words

TTS models default to a flat read - technically correct, dramatically dead. Two separate
annotation passes exist to fight that, aimed at the two different places delivery comes from:

**1. What to say it like.** Every one of the 45,114 previously-unvoiced lines has been run
through an LLM annotation pass (14B model, with a per-companion character bio for context) that
tags emotion, pace, and a short delivery instruction alongside the text itself. The runtime mod
resolves this per line and passes it to the voice server, which translates the neutral tags into
whatever directive format the active engine actually responds to.

**2. What to clone from.** Zero-shot voice cloning inherits the prosody of whatever reference
clip it's given - clone a companion's voice from one calm, neutral line and every emotion comes
out sounding calm and neutral, tags or no tags. So instead of one reference clip per character,
the goal is a small bank of reference clips per character *per emotion*, pulled from that
character's own official voiced lines. Coverage is tracked on a local dashboard (every
character/emotion combination the corpus actually needs, ranked by how many lines depend on it),
and each candidate clip gets a human listen-and-decide pass before it's accepted into the bank:

![Emotion coverage dashboard, tracking which character/emotion reference banks are done, need review, or are still unrepresented](docs/images/emotion-coverage-dashboard.png)

![Clip curation tool: a human accepts or rejects each candidate reference clip by ear, alongside the LLM's text-based emotion label and an independent audio-based (emotion2vec+) score for agreement](docs/images/emotion-clip-curation.png)

*Snapshot as of 2026-09-09, not a finished count - the corpus keeps growing.* Like everything
else here, this only touches your own locally-extracted game audio, never anything redistributed.

## How the annotations are checked

An LLM tagging 45,114 lines with an emotion isn't automatically trustworthy - it's easy to end
up with labels that are confident, consistent, and wrong. A few concrete things this pipeline
does about that:

- **A hand-checked gold set** of 255 lines across 14 conversations (every companion plus the
  narrator), with its own scorer, tracks how well the automated annotator agrees with a human
  reading the same lines.
- **The annotator model was upgraded after failing on real examples, not preemptively.**
  Spot-checking real output caught a devout "the God-Emperor's blessing" declaration tagged
  `amused`, and a sadistic character quietly relishing a torture victim's pain tagged flat
  `neutral` - both cases where the annotator had no character context, just a bare speaker name.
  Fixing that (per-character bios fed into the prompt) plus moving from an 8B to a 14B model
  fixed both cleanly; the 8B model with bios fixed them too but introduced a new miss nearby,
  which is why 14B is the one actually used.
- **A 78-line stratified audit of the real bulk output** (not just the curated gold set - 30
  speakers, all 12 emotions represented) came back about 88% clean, with the one real systematic
  defect it found - sarcastic/mocking lines occasionally mistagged by the emotion enum - fixed by
  a targeted reconciliation pass, not a full re-run.
- **That fix corrected its own mistake.** The first version of the sarcasm fix over-matched on
  bare words like "mocking," which flattened some genuinely angry or manic lines into
  `sarcastic` too. Auditing the actual corrected lines (not just re-checking the ones it got
  right) caught this, and the keyword set was narrowed until all 92 corrections held up on
  manual review.

## Choosing the TTS engine

Published benchmarks don't tell you which engine actually sounds best on real annotated Rogue
Trader lines, so there's a local tool for comparing them head-to-head instead of guessing: the
same line, all engines side by side and labeled (not blind), ranked best-to-worst with a Borda
count, plus per-clip error tagging (mispronunciation, wrong emotion, doesn't match the reference
voice, and so on).

![Listening test standings: engines ranked by Borda count across voted lines, with a reference line and its official-VO reference audio shown above the ranking clips](docs/images/listening-test-standings.png)

![Listening test ranking UI: five labeled engine clips for one line, each with checkboxes for specific error types](docs/images/listening-test-clips.png)

*Standings as of 2026-09-09 - an early sample, not a final result.* No engine ships with this
mod (see [what's in the download](#how-this-differs-from-other-rogue-trader-voice-mods)), so
what this decides is a *recommended* engine, not a shipped one - you pick and install whichever
engine you want, this just tells you which ones are actually good. Seven engines and variants
have gone through this so far, including one - Higgs TTS 2 - kept in purely as a quality
reference despite a restrictive license and heavy VRAM footprint that would make it a bad
recommendation regardless of what we say about it here.

## Where the TTS engine runs

The runtime mod never synthesizes audio itself - it sends `{text, speaker, annotation}` to a
voice server over HTTP and gets back a WAV. That's the whole design point: the game and the
voice server are always separate processes speaking the same protocol, so where each one runs
is a deployment choice, not an architecture choice. Same machine is the simplest setup and the
only one that works today (see below); a second machine on your LAN, or even a different OS on
each side, is meant to work exactly the same way once that's built.

The voice server's engine backend does vary by platform - Python/PyTorch/GPU on Linux (working
today, you install the Python/CUDA stack and whichever engine you picked yourself), ONNX Runtime
on Windows (planned, avoids needing Python/CUDA installed at all - see `PROJECT_PLAN.md`).
Neither ships model weights: the Windows server loads whatever ONNX-format engine weights you
put in its folder, the same way the Linux one loads whichever engine you installed. Both talk
the same `/synth` protocol, so a Windows game client can point at a Linux voice server, a Linux
client can point at a Windows one, and so on. macOS support for
*running* the voice server itself is unresearched (Apple's Core ML/MLX stack, unproven for any
of the bake-off's candidate engines); a macOS game client pointing at a Linux or Windows voice
server on the LAN needs nothing new once that mode ships.

Today, none of that is built yet: the voice server's bind address and the mod's server URL are
both hardcoded to `127.0.0.1`, so it has to be the same PC as the game. Handing synthesis off to
a second machine - a spare-GPU box while the game runs on something lighter, in either direction
- is planned but not started. When it lands: a mod-menu field for the server's address, no
built-in authentication (this is for your own trusted home network - don't port-forward it to
the internet), and a line that fails to get audio back in time gets skipped rather than stalling
dialogue, with a brief in-game notice instead of a silent gap.

## Design decisions

- Fork of Osmodium's SpeechMod hook layer (MIT), new `ITtsBackend`/`IAudioOutput` seam.
* Game and voice server are always separate processes over HTTP (GUID-keyed disk cache,
  graph-lookahead prefetch to hide latency) - same machine today, LAN-splittable once that
  ships. See [Where the TTS engine runs](#where-the-tts-engine-runs).
- Offline pipelines: dialogue export → LLM emotion annotation (`annotations.<locale>.json`) →
  runtime dictionary lookup. 40K phonetic lexicon applied per engine (IPA where supported,
  respelling otherwise).
- Voiced lines (`Sound.json`) never get re-synthesized, official VO always wins over anything
  generated.
- Voice cloning from your own game files happens locally and is opt-in - no cloned voice data
  is ever distributed. No engine or voice data ships with the mod either (see the comparison
  table above), so a non-cloned voice is just whatever generic voice your chosen engine ships
  with - the mod doesn't add one on top.
- Planned: synthesize the player character's own dialogue in whatever voice they picked at
  character creation - not a generic "protagonist" preset, the specific voice for the specific
  character you made. Mod menu will let you turn it off, or re-pick the voice later, if you'd
  rather not hear your own lines read back.

## Install

Not released yet, but here's the shape of it so it's not a mystery. Full instructions land with
the first release.

- **Linux/Proton**: install Python, PyTorch, CUDA, and whichever supported TTS engine you want
  (a setup script is planned to make this closer to one command); the voice server runs
  alongside the game. More setup than a plug-and-play mod, in exchange for choosing your own
  engine instead of being stuck with whatever shipped.
- **Windows**: drop your chosen engine's ONNX-format weights into the voice server's folder.
  No Python/CUDA toolkit needed.
- A player who does neither of those gets no voice for unvoiced lines - there's no robotic
  fallback voice, on purpose (see [Design decisions](#design-decisions)).

## Layout

| Path | What |
|---|---|
| `src/DialogueExporter/` | UMM mod: dumps the game's dialogue blueprint graph to `script.json` (run once at the main menu) |
| `src/RogueTraderNeuralSpeechMod/` | The runtime mod (UMM): hooks dialogue, resolves annotations, calls the voice server, plays back audio |
| `src/TtsSidecar/` | The voice server (Linux/Python/GPU today): text + speaker + annotation → synthesized PCM, per-engine directive translation |
| `tools/extract_localization.py` | Localization strings + voiced map + 40K vocabulary worklist |
| `tools/build_conversations.py` | Walks the cue graph into ordered, speaker-attributed conversation scripts |
| `tools/unpack_pck.py`, `tools/extract_voice_lines.py` | Wwise `.pck` → speaker-attributed WAV clips of the official VO (stays on your machine) |
| `tools/build_prompt_banks.py` | Picks clean reference clips per speaker for zero-shot voice cloning |
| `tools/build_test_set.py` | Fixed 142-line bake-off set (unvoiced lines per companion + narration) |
| `tools/tts_bakeoff/` | Runs candidate TTS engines over the test set; scores speaker-similarity + WER |
| `tools/annotate/` | LLM annotation harness: emotion/pace/non-verbal/instruct labels per line, engine-neutral schema |
| `tools/score_catalog_emotions.py` | Audio-based emotion scoring (emotion2vec+) of the official VO clips, checked independently against the LLM's text-based read |
| `tools/emotion_review/` | Local dashboard + listen-and-decide tool for curating per-character, per-emotion reference-clip banks |
| `tools/audio_match/` | Fits an EQ/compression profile from real VO vs. generated clips to closer-match a TTS engine's output |
| `tools/listening_test/` | Local labeled listening-test server: ranks engines head-to-head per line, tallies a Borda count |
| `docs/research/` | Ecosystem research reports |

## Building the exporter (Linux)

```
export DOTNET_ROOT=$HOME/.dotnet PATH=$HOME/.dotnet:$PATH
dotnet build src/DialogueExporter -c Release -t:Deploy   # paths in Directory.Build.props
```

## Credits

Wouldn't exist without this prior art:

- [SpeechMod](https://github.com/Osmodium/W40KRogueTraderSpeechMod) by Osmodium (MIT) - hook architecture
- [W40KRT_AIVOMod](https://github.com/pas2k/W40KRT_AIVOMod) by pas2k (MIT) - Wwise VO-shim approach, wwnames trick
- [Ripcy's RSpeechMod](https://www.nexusmods.com/pillarsofeternity/mods/430) for *Pillars of
  Eternity* - proof that live, in-process neural TTS inside a UMM-modded Unity game works at all
  (sherpa-onnx running Piper/Kokoro). No license attached to its source, so reference material,
  not something this mod builds on.
- [wwiser](https://github.com/bnnm/wwiser) by bnnm and [vgmstream](https://vgmstream.org) - dev-only
  Wwise bank extraction tools, not bundled in any release. See `THIRD_PARTY.md` for the full
  attribution/licensing detail on both.
