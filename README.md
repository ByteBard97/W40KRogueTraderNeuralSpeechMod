# W40K Rogue Trader — Neural Speech Mod

Live, local, neural text-to-speech for the ~90% of Warhammer 40,000: Rogue Trader that ships
unvoiced. Per-character voices, emotion-annotated delivery, Linux/Proton first.

Status: full corpus annotated (**45,114** previously-silent lines, emotion/pace/delivery labeled
per line) and generating audio end-to-end. Currently in listening-test quality verification
before locking the default engine and cutting a first release. See `PROJECT_PLAN.md` for the
full living plan and detailed progress log.

## Layout

| Path | What |
|---|---|
| `src/DialogueExporter/` | UMM mod: dumps the game's dialogue blueprint graph to `script.json` (run once at the main menu) |
| `src/RogueTraderNeuralSpeechMod/` | The runtime mod (UMM): hooks dialogue, resolves annotations, calls the TTS sidecar, plays back audio |
| `src/TtsSidecar/` | Local Python/GPU server: text + speaker + annotation → synthesized PCM, per-engine directive translation |
| `tools/extract_localization.py` | Localization strings + voiced map + 40K vocabulary worklist |
| `tools/build_conversations.py` | Walks the cue graph into ordered, speaker-attributed conversation scripts |
| `tools/unpack_pck.py`, `tools/extract_voice_lines.py` | Wwise `.pck` → speaker-attributed WAV clips of the official VO (stays on your machine) |
| `tools/build_prompt_banks.py` | Picks clean reference clips per speaker for zero-shot voice cloning |
| `tools/build_test_set.py` | Fixed 142-line bake-off set (unvoiced lines per companion + narration) |
| `tools/tts_bakeoff/` | Runs candidate TTS engines over the test set; scores speaker-similarity + WER |
| `tools/annotate/` | LLM annotation harness: emotion/pace/non-verbal/instruct labels per line, engine-neutral schema |
| `tools/audio_match/` | Fits an EQ/compression profile from real VO vs. generated clips to closer-match a TTS engine's output |
| `tools/listening_test/` | Local labeled listening-test server: ranks engines head-to-head per line, tallies a Borda count |
| `docs/research/` | Ecosystem research reports |
| `reference/` (gitignored) | Clones of prior art: Osmodium SpeechMod (MIT), pas2k AIVO (MIT), Ripcy RSpeech (no license — study only) |

## Design (agreed so far)

- Fork of Osmodium's SpeechMod hook layer (MIT), new `ITtsBackend`/`IAudioOutput` seam.
- TTS runs in a local sidecar server (GPU, Python) with a GUID-keyed disk cache;
  graph-lookahead prefetch hides latency. In-process ONNX backend later.
- Offline pipelines: dialogue export → LLM emotion annotation (`annotations.<locale>.json`) →
  runtime dictionary lookup. 40K phonetic lexicon applied per engine (IPA where supported,
  respelling otherwise).
- Voiced lines (`Sound.json`) are never re-synthesized; official VO always wins.
- Voice cloning from the player's own game files happens locally and is opt-in; no cloned
  voice data is ever distributed. Shipped default voices are synthesized from scratch.

## Building the exporter (Linux)

```
export DOTNET_ROOT=$HOME/.dotnet PATH=$HOME/.dotnet:$PATH
dotnet build src/DialogueExporter -c Release -t:Deploy   # paths in Directory.Build.props
```

## Credits

- [SpeechMod](https://github.com/Osmodium/W40KRogueTraderSpeechMod) by Osmodium (MIT) — hook architecture
- [W40KRT_AIVOMod](https://github.com/pas2k/W40KRT_AIVOMod) by pas2k (MIT) — Wwise VO-shim approach, wwnames trick
- [wwiser](https://github.com/bnnm/wwiser) by bnnm — dev-only tool for local Wwise bank extraction,
  **not bundled**: the repo has no LICENSE file granting redistribution rights, so contributors
  must download it themselves (link above) rather than vendor the binary in a release zip
- [vgmstream](https://vgmstream.org) — ISC license (permissive, bundling-safe). Copyright (c)
  Adam Gashlin, Fastelbja, Ronny Elfert, bnnm, Christopher Snowhill, NicknineTheEagle, bxaimc,
  Thealexbarney, CyberBotX, EdnessP, and contributors, with portions by Marko Kreen, jagarl,
  Nullsoft, Paul Hsieh, Lesahde Entis, and Sun Microsystems (see vgmstream's `COPYING`). Official
  prebuilt CLI binaries exist for Windows/macOS/Linux, so per-OS bundling is viable once a
  release needs it — check whether the vendored build links LGPL components (mpg123, FFmpeg)
  dynamically or statically before shipping, per vgmstream's own `doc/BUILD.md`.
