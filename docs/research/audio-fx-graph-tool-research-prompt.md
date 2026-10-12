# Research prompt: node-graph audio FX tool with live tweaking and scriptable batch processing

Hand this to web research agents. Split by the angles at the bottom if running several in parallel.

## Context

We have ~11,000 TTS-rendered dialogue lines (mono WAV, 24-48 kHz, a few seconds each) for a game mod. Different speakers
need different post-processing: servitors, vox-casters, ghosts, machine spirits, tech-priests, intercoms. Today we have
a hand-written chain (highpass, lowpass, drive, bitcrush, ring mod, tremolo, echo, reverse reverb) in Python/numpy with a
JS mirror for in-browser preview. It is a fixed serial chain with one global wet/dry knob. It is outgrowing that.

## What we want

Two workflows on the same effect definitions:

1. **Experiment interactively.** Load a rendered clip, loop it, and turn knobs live while it plays until it sounds right.
   Wire effects in a signal-flow diagram (visual node graph preferred, but a rack/chain UI with parallel lanes is fine).
2. **Script the result.** Once a pipeline and its settings are chosen, save it (JSON, preset file, patch file, anything
   machine-readable), then run a script that loops over our clips, loads the right pipeline and parameter set per
   clip or per speaker, and writes processed WAVs. Headless, no GUI, no human in the loop, thousands of files.

## Hard requirements

- **Series and parallel routing.** Split a signal into branches, process each differently, and recombine.
- **A convex-combination mix block usable anywhere in the graph:** `out = a*A + (1-a)*B`, with `a` adjustable, where A can
  be the raw original signal and B the output of any processing chain. Not just one wet/dry knob at the end. If a tool
  only offers per-effect wet/dry that blends with that effect's own input, say so; that is a partial match.
- **Scriptable offline batch rendering** from Python, Node, or a CLI. Faster than realtime is a strong plus.
- **Per-file parameter control from the script.** We need to change knob values per clip without hand-editing the
  patch each time.
- **Runs on Linux** (primary: Ubuntu-like). Desktop app, web app, or self-hosted web page all acceptable.

## Nice to have

- Open source (preferred, not required). Commercial or freemium is fine if batch scripting is genuinely possible and
  the license allows scripted use. State the license and price either way.
- Live parameter changes without audio glitches while a file loops.
- Visual graph that is also the saved format (so the diagram and the script cannot drift apart).
- Latency/delay compensation between parallel branches so that dry/wet blends do not comb-filter. If absent, note it.
- Effect library broad enough to cover: filters, distortion/waveshaping, bitcrusher, ring modulator, tremolo, delay/echo,
  reverb (including reverse reverb if anyone has it), pitch shift, chorus/flanger/phaser, compressor, EQ.
- Guitar and music effects are fine. The effects do not need to be tuned for speech; we only need them to be good
  building blocks.
- Can host VST3/LV2/CLAP plugins, so we can borrow free guitar-effect plugins.

## Candidates to check first (verify; do not assume they work)

- Browser: JSPatcher, WebAudioDesigner, audio-diagrams, NoiseCraft, Tone.js-based editors, Faust IDE / FaustWasm,
  WebPd, Elementary Audio, cables.gl.
- Python: Spotify Pedalboard (check `Mix`/parallel semantics and whether the Mix weights are adjustable), voicebox
  (`ParallelChain`, `dry_gain`), pyo, Faust via faust2... or `dawdreamer`, `pyfaust`, `pedalboard` + VST3.
- Graph/DAW-like with headless render: DawDreamer (graph of processors, offline render from Python), Cardinal / VCV Rack
  headless, Carla (LV2/VST host with patchbay and CLI), Pure Data / Purr Data driven offline, SuperCollider NRT
  (non-realtime) mode, Csound, SoX, FFmpeg filtergraph, Ardour/Reaper headless render (Reaper has ReaScript and
  command-line render), Bitwig/other DAWs only if scriptable.
- Plugin-host approach: a free guitar-multi-effects plugin chain (e.g. Guitarix, Airwindows, TAL, Dragonfly, Calf,
  ZynAddSubFX effects) hosted through Pedalboard, DawDreamer, or Carla.

Look beyond this list. Search GitHub, awesome-lists (awesome-webaudio, awesome-audio-dsp, awesome-music-production),
Hacker News, r/audioengineering, r/WeAreTheMusicMakers, r/synthdiy, KVR forums, and Stack Overflow for phrases like
"node-based audio effects editor", "batch process audio with modular patch", "headless render patch".

## What to report back

Per candidate, short and factual, with links:

| Field | Notes |
|---|---|
| Name, link, license, price | |
| Live tweak on a looping file? | yes / no / how |
| Visual graph? | node graph / rack / none |
| Parallel + convex mix `a*A+(1-a)*B` | native, buildable with N blocks, or not possible |
| Headless batch render | how (API call, CLI flag), tested or just documented |
| Per-file parameter override | how |
| Linux support | |
| Maintenance | last release/commit date, open issue count |
| Effect coverage | which of our list it has |
| Verdict | strong fit / partial / reject, and why |

Then:

- A ranked shortlist of 3 to 5, plus the best way to combine two tools if no single one covers both workflows (for
  example "design in X, export patch, render with Y").
- For the top picks, a minimal code or command example showing batch rendering with a per-file parameter, copied from
  docs or an issue, with the link. Flag anything you did not see work yourself.
- Anything you checked and ruled out, with one line on why, so we do not redo it.

## Ground rules for the agents

- Mark every claim as verified (read in docs or source) or unverified (inferred from a listing or a forum post).
  Do not report a feature as supported on the strength of a product page alone; look for docs, source, or an example.
- Prefer primary sources (repo README, docs, release notes) over blog summaries.
- Check dates. Many audio tools are abandoned; say when something has not been touched in over two years.
- If a candidate fails the series/parallel/convex-mix or the headless-batch requirement, say which and stop; do not pad
  the report.

## Suggested split for parallel agents

1. Browser-based node editors and Web Audio / Faust / Pd-in-browser tools.
2. Python and Node libraries with scriptable parallel graphs (Pedalboard, DawDreamer, voicebox, pyo, Elementary).
3. Desktop hosts and DAWs with headless or CLI render (Carla, Reaper, Ardour, Cardinal, SuperCollider NRT, Csound, Pd).
4. Free guitar/music effect plugin collections that can be hosted by approach 2 or 3, with licenses and Linux builds.
