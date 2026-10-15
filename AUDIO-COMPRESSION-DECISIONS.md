# Audio compression: what we tested and decided

Written 2026-10-13, covering the session of 2026-10-12. Background and the research behind it are in
`docs/research/audio-compression-and-runtime-decoding.md`. This file records results and decisions only.

## The problem

The installed bank stores our audio as uncompressed PCM wems (24 kHz mono 16-bit, `WAVE_FORMAT_EXTENSIBLE`). The full set is
about 19 GB (7 bank files, 31,186 clips). The AIVO mod loads every bank at startup, so all of it is resident for the whole
session. Memory use at this size has never been measured.

## What we tested in the game (confirmed)

Tested with the Format Tester mod (`tools/format_tester`, numpad hotkeys, on-screen report, `results.jsonl`). All four test
lines used the same narrator audio and differed only in how the wem was described to Wwise.

| Test | Wem | Result |
|---|---|---|
| Line A | Opus, codec plugin `0x00140001` (AKOPUS_WEM) | Played. Engine duration 24.96 s, same as the source WAV. |
| Line B | Opus, plugin `0x00130001` (AKOPUS) | Played. Duration 17.44 s, same as the source. |
| Line C | Opus, `cbSize` 16, plugin `0x00140001` | Played. Duration 12.00 s, same as the source. |
| Line D | PCM control | Played. |
| `SetMedia` | PCM wem pushed over line D's media, which was already loaded in the installed bank | Worked. Reported duration was the pushed clip's (24.96 s), not the bank's (23.68 s). |
| `UnsetMedia` while the voice played | | `AK_ResourceInUse`. The voice stopped. A second call returned `AK_Success`, and the bank's original media played again. |

Heard by the user: lines A, B and C all audible, the `SetMedia` override audible (the user could not tell the line's words
apart from the narrator, so the evidence for the override is the reported duration), and the original line after unsetting.

## Decisions

1. **Opus is the codec.** Wwise Opus wems play in this game's engine. Speech at 24 kHz mono is a good fit: about 13x smaller
   than PCM, so about 1.5 GB for the current set instead of 19 GB, and the side banks are probably no longer needed.
2. **Plugin id `0x00140001` (AKOPUS_WEM), default header.** It is the standard one and A played. `0x00130001` and the
   `cbSize` 16 header also work, so nothing forces a change if a later build uses either.
3. **Opus in the banks is the first route.** It needs no mod code, and it fixes disk size and memory at once. It is the
   smaller change of the two routes that work.
4. **The rendered WAVs stay the master.** Encode from the WAVs at build time. Never re-encode from Opus files.
5. **Keep the current PCM set moved aside, never deleted,** until an Opus build has been played through for a while
   (`soundbanks_disabled/`).
6. **Do not gate rendered content out of a build without asking** (the 11,205 codex/item strings were withheld earlier over an
   unmeasured RAM worry). If Opus makes the full set small enough, this stops being a question.

## Not decided yet

- **Bitrate.** Candidates are 16, 24 and 32 kbps. This is the one choice that is expensive to redo, because a change
  means rebuilding the whole bank. Plan: encode a few real lines (sibilants, quiet and breathy delivery) at each
  rate, stage them as extra hotkeys in the tester, and compare by ear against the PCM control. The 16 to 24 kbps range is an
  estimate, not a measurement.
- **Loudness.** The gain is applied before encoding, so re-verify levels after the switch.
- **Whether to run a full-size Opus bank in the game** before replacing the installed set. Recommended: build one, play it,
  then replace.

## Second route, kept in reserve: runtime decoding

`SetMedia` over loaded media works, so the mod could keep clips compressed on disk, decode a line just before it plays
(Concentus for Opus, on a worker thread, queue drained from UMM `OnUpdate`), and hand PCM to Wwise. Re-renders would become a
file swap with no bank rebuild.

What the tests showed about the lifecycle:
- Wait until the line has finished, or stop it, before unsetting.
- `UnsetMedia` on a playing voice stops it and returns `AK_ResourceInUse`. Call it again with nothing playing, and only
  free the buffer after `AK_Success`.
- Use `Marshal.AllocHGlobal` aligned to 16, not a pinned managed array.

Not tested: the memory saving with media-stripped banks, decode time on this runtime, `SetMedia` on a source that has no media
in any loaded bank. Not worth building unless Opus in the banks falls short.

## Rejected

- **Wwise ADPCM.** About 4x smaller, noticeably worse quality on speech, and the wem header layout is unverified with no
  writer. Only a fallback if Opus had failed.
- **Wwise Vorbis in the bank.** Needs Wwise's authoring tool. No open encoder.
- **MP3.** Worse quality per byte than Opus, and padding complicates gapless timing.
- **FLAC.** Only 2 to 3x smaller, and it needs runtime decoding.

## Next steps

1. Bitrate comparison in the tester (16, 24, 32 kbps on a handful of lines).
2. Make `--codec opus` the build default in `night_build.py` / `patch.py` at the chosen bitrate, and re-check loudness.
3. Build the full bank, test it in the game, then replace the installed set (keep the PCM set aside).
4. Measure game memory with the Opus bank.

## Where things are

- Format Tester mod: `tools/format_tester/` (installed under `UnityModManager/FormatTester/`). Keypad 1 to 4 play the test
  lines (the installed main bank is swapped out until keypad 0 restores it), 5 and 6 run `SetMedia` / `UnsetMedia`, `+` and `-`
  record what you heard.
- Test bank builder: `tools/bnk_patch/tone_test3.py --only-new` (writes a small test bank, `tests.json`, and the override wem).
- Opus writer: `tools/bnk_patch/opus_wem.py`; bank patcher: `tools/bnk_patch/patch.py --codec opus`.
- Opus test bank (4 lines, 5 MB): `/home/geoff/rt-mods/format-tester-banks/`.
- Related: `docs/research/audio-compression-and-runtime-decoding.md`, `docs/research/silent-replaced-audio-brief.md`
  (the extensible PCM header), `docs/research/loudness-analysis-2026-10-11.md`.
