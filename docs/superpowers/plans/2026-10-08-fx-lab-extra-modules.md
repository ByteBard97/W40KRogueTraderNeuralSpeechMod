# FX Lab: extra modules (plan)

Goal: add the eight modules the three research reports surfaced to the FX Lab page (`tools/fx_lab/`, http://127.0.0.1:8908/) so each can be auditioned and used by `batch.py`. Source of the list: the 2026-10-08 comparison of the Gemini, Claude and Kimi reports. State before this plan: `faust/chain.dsp` (49 controls, 18 blocks), `null_test.py` (FaustWasm vs DawDreamer), `check_scenarios.py`, `batch.py`, `index.html` snake-grid page with a hard-coded `SLOTS` list and `GROUPS` regexes.

## Principle

Two kinds of module, because the page's live engine is causal and runs in the browser:

- **Live (Faust, in `chain.dsp`)**: parametric EQ, harmonizer, dropout chopper, wow and flutter, metal-box resonator. These get knobs, stomps, scenarios, a null test against DawDreamer.
- **Offline (needs the whole clip or a non-Faust library)**: pitch flatten and formant shift (pyworld/WORLD), reverse reverb (numpy), codec simulation (ffmpeg). The page cannot run these in its live graph.

## Live modules (Faust)

All follow the existing pattern: `stomp(on_X, f)` checkbox, controls tagged in signal order, a `GROUPS` regex and a `SLOTS` entry (a block missing from `SLOTS` silently does not render; that bit us once).

1. **Parametric EQ** (`EQ` block): three peaking bands (freq, gain dB, Q) plus a high shelf (freq, dB). `fi.peak_eq(gain, freq, bw)`-style or RBJ biquads via `fi.tf2`; off when gain = 0. Position: right after de-ess (subtractive clean-up before pitch), i.e. before the nonlinear stages.
2. **Harmonizer** (`Harmonizer` block): two extra pitch-shifted voices in parallel with the dry path: semitones and level each. Uses `ef.transpose` twice. Each voice delayed ~20 ms by the shifter, so the dry branch gets a matching `de.delay` (so voices double, not comb) unless "layered" mode is chosen; keep it simple: dry path delayed by the same amount. Position: after the existing mono Pitch block.
3. **Dropout chopper** (`Dropout` block): a gate that mutes the signal in short random bursts: rate (events per second), length range ms, depth. Must be deterministic across runtimes for the null test: drive from a fixed-seed pseudo-random sequence generated from a sample counter (an LCG in Faust), not `no.noise` (whose seed differs per runtime). Position: late, after drive/crush/ring (after the "speaker"), before echo/reverb (the fault is in the transmission, per Voquent).
4. **Wow and flutter** (`Wow flutter` block): pitch modulation by a modulated delay line: wow rate/depth (0.5 Hz) and flutter rate/depth (7-12 Hz), depth in cents. Position: after chorus (modulation block), before the phaser.
5. **Metal-box resonator** (`Resonator` block): bank of 4 fixed resonant band-pass filters (freqs, Q, mix) summed with the dry signal, to approximate a small-metal-object impulse response (grille, tin, helmet). Position: after the compressor/drive, before ring mod. Frequencies adjustable, defaults from a rough "metal box" set (e.g. 700, 1900, 3100, 4600 Hz).

Page: `SLOTS` grows from 20 to 25 items, so the snake grid becomes 5 rows of 5. `GROUPS` gets EQ, Harmonizer, Dropout, Wow/flutter, Resonator regexes. The signal-flow comment and `dsp` header updated.

## Offline modules and how they reach the page

Add `tools/fx_lab/offline.py` with pure functions on numpy arrays, all with unit tests:

- `world_process(x, sr, flatten, f0_hz, formant_semitones)`: pyworld analysis (f0, spectral envelope, aperiodicity) then resynthesis with the f0 contour flattened to a constant (or quantised) and the spectral envelope frequency-warped for formant shift. Needs `pip install pyworld` into `.venv-fx` (sdist builds with gcc; gcc/g++ present, wheels not available). Risk: build failure; fallback is `librosa`-free numpy pitch tracking, or dropping the module. Spike this first.
- `reverse_reverb(x, sr, decay, mix)`: port of the numpy `fx.py` version (reverse, Schroeder reverb, reverse), already exists in `tools/voice_design/fx.py`; reuse it.
- `codec(x, sr, kind)`: ffmpeg round trip through G.711 mu-law at 8 kHz, G.726 ADPCM, or low-bitrate libmp3lame (no GSM encoder in this ffmpeg build). Resample back to the original rate.

Order in `batch.py`: `world_process` first (clean source), then the live chain (DawDreamer), then `reverse_reverb`, then `codec`, then trim and loudness match. Presets get an optional `"offline": {...}` section next to `"params"`.

Page integration: an **"Exact render"** button and an offline-controls panel (flatten on/off + Hz, formant semitones, reverse reverb decay and mix, codec choice). The live graph in the browser plays the currently selected clip with the live modules only. "Exact render" POSTs the clip id, `params` and `offline` to a new server endpoint that runs the same code path as `batch.py` (a shared `process_clip`) and returns a WAV the page plays in place of the live graph (with a clear "exact render, not live" indicator). The server needs the `.venv-fx` Python for DawDreamer, pyworld, scipy; today `server.py` runs under the system python, so the endpoint either shells out to `.venv-fx/bin/python` or the server is started under it. Decision: start the server under `.venv-fx` (it uses only stdlib otherwise).

## Verification

- `null_test.py` gets a case per live module (deterministic only; no `no.noise`).
- A behaviour test per module: EQ band changes the spectrum where set; harmonizer adds energy at the expected f0 ratios; dropout mutes the expected fraction of time with the same pattern in both runtimes; wow/flutter measurable pitch deviation; resonator adds the expected peaks.
- `offline.py` unit tests: pitch-flatten reduces f0 variance on a synthetic chirp; formant shift moves the envelope peak; reverse reverb pre-echo present (existing test in voice_design); codec output length equal and spectrum band-limited (8 kHz mu-law).
- `check_scenarios.py` extended to run the batch pipeline (`unclip` + loudness match) so numbers match what lands in the bank.
- Playwright page test: all groups render, knob count matches, scenarios load, Exact-render button returns audio.

## Scenarios (starting presets, to tune by ear)

Add scenarios using the new modules: Pasqal-style stack (harmonizer -12/+7 plus vocoder, as a start for matching the in-game Pasqal), daemon (harmonizer layers), flat servitor (pitch flatten + vocoder), hologram (wow/flutter + dropout + codec), helmet with EQ presence boost, vox-grille (resonator).

## Stop points

1. After the pyworld spike (does it build, does flatten sound sane on a clip) report before building the rest of the offline side.
2. After the live modules and their tests, surface the page for listening before the Exact-render plumbing.
3. Not in scope: granular, stereo, convolution with real IR files, the macro-control layer, automatic matching of the Pasqal effect (a separate task).
4. Then return to the voiceless-NPC list (`TODO.md`, `memory/return-to-voiceless-npcs.md`).

## Advisor review (2026-10-08) and what changed

- Dropout determinism: checked, `no.noise` is bit-identical between FaustWasm and DawDreamer (both fixed-seed generators), so dropout uses it directly (coin flip held on each period start) and static is now in the null test. No LCG.
- Harmonizer: `ef.transpose` is two sweeping delay lines, not a fixed latency, so the copies are described as "layers that double the dry", not aligned. Global Mix vs Pitch offset stays documented, not compensated.
- pyworld: sdist only; install needs cython and `--no-build-isolation` against the venv's numpy; fallback is resample plus `ef.transpose`; pitch-flatten can be dropped (TTS is already flat).
- Notes applied: `peak_eq` takes bandwidth in Hz (f/Q); cents-to-delay conversion in wow/flutter; resonator sits between drive and crush; new control prefixes checked against the `GROUPS` regexes.
- Stop point held: live modules done; offline modules and the Exact-render endpoint wait until the user has listened.
