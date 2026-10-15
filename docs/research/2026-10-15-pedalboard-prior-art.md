# Pedalboard canvas: prior art, licensing and sharing readiness

Date of research: 2026-10-15. All GitHub metadata below was read from the GitHub REST API on that date (stars, pushed_at, license field). License texts were read from the raw files unless marked otherwise. "Not found" means my searches did not turn it up; it does not mean it does not exist. Search coverage was a few dozen web searches and fetches, not an exhaustive survey.

## Short answer

1. The pieces are not novel. Turning a patched graph into one Faust expression is in Faust Playground's source (grame-cncm, since about 2016). A current visual editor, FaustWave, generates Faust source from a graph in the browser and recompiles on rewiring. FaustMod and nagi are further canvas-plus-Faust tools. Ozone-class tools overlay a reference spectrum.
2. What I could not find anywhere: (a) the saved generated program being reused by an offline batch renderer so the browser sound is reproduced on bulk files, (b) an overlay of a processed clip's average spectrum plus L/R correlation and side/mid against a reference recording, built for matching one target voice, (c) a crossfade when the graph recompiles (FaustWave stops, recompiles, starts).
3. The combination as a workflow (tune by ear and numbers in the browser, then render hundreds of lines identically) looks unclaimed, but each of its parts is ordinary. It is a solid specialist tool, not an invention.
4. It is likely useful to a small audience: Faust users and voice-processing modders. Demand outside this project is unproven (see section 4).
5. Worth sharing in a modest form: a static browser demo with a few starter presets and a short capture, announced in the Faust community and one modding venue. A Show HN is possible but expect little; comparable audio-tool posts mostly land in single digits. Do not frame it as novel in the large.

## 1. Prior art: browser and visual audio-effect graph editors

### 1.1 Faust-based tools (closest)

| Project | What it is | License | Last push / stars | Notes |
|---|---|---|---|---|
| Faust Playground (grame-cncm/faustplayground) | Browser patcher for Faust modules, built for teaching | LGPL-2.1-or-later (COPYING.txt header read) | 2026-10-02, 33 stars | Maintained at a low rate. See 1.2. |
| FaustWave (faustwave.io) | Desktop app plus browser IDE: visual graph and Faust source side by side, mixer, sequencer, recorder, analysis nodes | Software license not stated on pages I could read; docs text is CC BY 4.0 | Early access v0.93.0 (site) | Closest functional match. See 1.3. |
| FaustMod (thepacket/faustmod) | Browser modular synth: node canvas of about 700 precompiled Faust blocks | GPL-3.0 (API), README says MIT until July 2026 | pushed 2026-09-02, 6 stars, created 2026-07-21 | Each block is its own AudioWorklet, cables are Web Audio connections. Not fused. |
| nagi (minimal-instruments.com) | Local-first app, node graph plus Faust source, browser preview, builds VST3 and CLAP | Commercial, free download, "public beta" | n/a | Page does not say whether the graph becomes one program. Not confirmed. |
| cdp-web (cdp-wasm-suite/cdp-web) | Retro-styled node graph for the CDP audio engine, embeds faustwasm for custom nodes | AGPL-3.0-or-later (vendored parts keep LGPL/MIT) | 6 stars, 13 commits | Tiny. Shows faustwasm is being vendored in AGPL web apps. |
| Faust IDE (grame-cncm/faustide) | Text IDE, compiles in browser, exports WAM and others | "Other" (NOASSERTION) | pushed 2026-10-01, 117 stars | Text only, no canvas. |
| Faust Editor / faustwasm | Library and simple editor | faustwasm LGPL-2.1 | faustwasm pushed 2026-10-14, 53 stars | faustwasm is the compile engine the owner uses. |
| Web Synth (Ameobea/web-synth) | Browser DAW and modular platform with a graph editor; supports dynamic Faust and Soul compilation | "Other" (NOASSERTION) | pushed 2026-08-13, 580 stars | Graph editor of Web Audio nodes plus Faust modules. Not a single fused program (not verified in detail). |
| Faust in Cables.gl | Listed on Faust "Powered by" page (video only) | n/a | n/a | I could not verify what it does. |

### 1.2 Faust Playground, how it really works

The README does not describe the UI. I read the source layout and one module. The repo has `src/Connect.ts`, `src/Dragging.ts`, `src/EquivalentFaust.ts`, `src/ExportLib.ts`, `src/CodeFaustParser.ts`. A fetch of `src/EquivalentFaust.ts` returned this summary of its behaviour (summary produced by the fetch tool, not a line-by-line read by me):

- It converts a patch graph into a single Faust expression. `createTree` walks back from the output module along input connections; `computeModule` emits text; `getFaustEquivalent` assembles the program.
- Sibling inputs are joined with `,`, merged with `:>`, with a `stereoize(p)` helper to adapt mono or other channel counts to stereo, and recursion (feedback) is emitted with `~`.
- Each module source is wrapped as `stereoize(environment{...}.process)` and the final line is `process = vgroup("patchName", (...));`.

So: parallel routing, merge, stereo adaptation and a named vgroup wrapper already exist in the Playground's equivalent-program generator. This is the same idea as the owner's generator in spirit. Differences visible from the plan: the owner uses layered `route()`, per-node `vgroup` ids, a fixed 2-in 2-out contract per node, an explicit Mix node, a cycle ban, and a keyed parameter scheme. Whether the live Playground audio runs the fused program or per-module Web Audio nodes was not confirmed from the sources I read. Treat "Playground only chains modules" as wrong; treat "Playground runs one fused program live" as unconfirmed.

### 1.3 FaustWave, the most important finding

Read from faustwave.io, its docs index and `llms-full.txt` (first 100k characters of 330k):

- "A visual patch editor whose graph is real Faust code you can read at any moment."
- Builder docs: "the Builder generates Faust source from your graph in real time." Topology changes "trigger a `stop → recompile → start` cycle." Parameter changes are smooth. No general crossfade on rewiring in the part I read.
- Stereo: output has `in_l` and `in_r`; stereo-aware nodes declare `channels: 2`; mono nodes work in stereo chains. A stereo pair draws a thicker cable.
- Save format: `.builder` JSON in the project's assets folder, git-trackable. No separate preset system in the part I read.
- Analysis pack: spectrum, FFT, mid-side goniometer, true-peak, Goertzel nodes. No reference-recording overlay seen in the part I read.
- Recorder: real-time capture of the master to 32-bit float WAV. No headless or batch render seen.
- Browser version at faustwave.io/ide/ exists (the page loads a "FaustWave IDE" shell; I could not see it run). No source repo or software license was visible, so it appears closed or at least unlicensed publicly.
- It is a young, solo-looking project at 0.93.0 early access. It is also directly adjacent to what the owner built, so anyone searching will find it. Look at it before announcing anything.

### 1.4 Web Audio Modules and Web Audio pedalboards

| Project | License | Last push / stars | Relevance |
|---|---|---|---|
| webaudiomodules/api (WAM 2.0) | none declared in API metadata | 2023-03-06, 205 stars | Plugin standard. Pedalboard-type plugins act as sub-hosts via WamGroup. Stale. |
| webaudiomodules/wam-examples | MIT (README) | 61 stars | Simple host, not a multi-plugin pedalboard. No Faust plugins listed in what I read. |
| boourns/wam-community | none declared | 2024-03-05, 47 stars | Prebuilt WAMs. |
| WAM pedalboard (Buffa et al.) | academic | papers 2018, 2022, WAM-studio 2023 | A series pedalboard host of WAM plugins; WAM-studio calls its plugin chain host the "WAM pedalboard". Built on Web Audio nodes, not one fused DSP program. |
| deermichel/pedalboard | GPL-3.0 | 2016-08-26, 54 stars | jQuery plus Tone.js guitar pedalboard. Dead. |
| RelientS/sonic-board | AGPL-3.0 | created 2026-08-27, 0 stars | Browser pedalboard, series and dual-path routing, WAM-free WASM circuit models, offline WAV export. Brand new. |
| dashersw/pedalboard.js | not checked | n/a | Guitar effects framework on Web Audio. |
| Audiotool, Amped Studio, Cables.gl | commercial / mixed | n/a | Browser DAWs or creative-coding tools. Audiotool has modular effect routing (their own marketing pages, unverified). Amped Studio supports WAM plugins. Cables.gl page not read. |

### 1.5 Other visual audio environments (all adjacent, none fits)

| Project | License | Last push / stars | Fit |
|---|---|---|---|
| Cmajor (SoundStacks) | "Other" (commercial options documented on site) | 2026-10-15, 756 stars | Has graphs of processors and exports HTML/JS WebAssembly. Text-first language, no canvas editor in what I read. Not Faust. |
| BespokeSynth | GPL-3.0 | 2026-10-14, 4,743 stars | Desktop modular. Not browser. |
| Cardinal (VCV Rack fork) | GPLv3+ (README) | maintained | README lists a Web standalone. Modular synth, not an effects-chain fit. |
| MOD Audio mod-ui | AGPL-3.0 | 2026-10-15, 114 stars | Web UI for the MOD hardware pedalboard (LV2 plugins on device). Serves graphs of plugins; no Faust-fused program. |
| Guitarix | no license in API | 2026-10-05, 655 stars | Desktop amp/effects. Not browser. |
| Pure Data on the web (Purr Data via GSoC 2020, pd4web) | various | n/a | Run Pd patches in browsers. Patching UI is Pd's. RNBO and Heavy not covered by my searches. |
| Spotify Pedalboard | GPL-3.0 | 2026-10-07, 6,355 stars | Python library, not a visual tool. Often confused by name. HN: 256 points (2021). |
| Csound web, SuperCollider web, SOUL | not investigated in depth | n/a | Not checked beyond a HN Show HN for SOUL 1.0 (see section 6). |
| shakfu/dsp-graph, gen-dsp | not checked | n/a | React Flow style graph editor that compiles to C++ for gen~ style DSP. Not Faust. From search summary only. |

### 1.6 "Graph to Faust" generators

Searches for node-graph-to-Faust code generators found: Faust Playground (1.2), FaustWave (1.3), nagi (unconfirmed), FaustMod (no, per-block worklets). No standalone open-source "graph JSON to Faust source" library turned up on GitHub searches I could run (GitHub code search is not available unauthenticated). That is a "not found", not a proof.

## 2. Is the specific combination novel?

| Element | Exists elsewhere? | Evidence |
|---|---|---|
| Faust blocks on a visual canvas | Yes | Playground, FaustWave, FaustMod, nagi |
| Graph compiled into one fused Faust program in the browser | Yes | Playground `EquivalentFaust.ts` (generator exists; live use unconfirmed), FaustWave (confirmed in docs) |
| Stereo-everywhere, route()-layered, vgroup-per-node, keyed parameters | Not found | Playground wraps with `stereoize` and a named vgroup; FaustWave uses L/R ports. Neither's internals matched the owner's contract in what I read |
| Live knobs plus recompile on rewire | Yes | FaustWave (stop/recompile/start) |
| Crossfade into the new compile so audio is not interrupted | Not found | FaustWave docs say stop, recompile, start. Not found in FaustMod (it avoids recompile by prebuilt blocks) |
| Saved generated Faust reused unchanged by an offline batch renderer (DawDreamer) | Not found | DawDreamer renders Faust offline and others use it for sound-matching; I found no tool where a browser editor's saved program feeds that. Queries tried: graph-to-Faust, browser Faust editor + DawDreamer, Faust node editor batch |
| Spectrum overlay against a reference recording | Yes for spectrum alone | iZotope Ozone Match EQ and spectrum meters overlay a reference; Voxengo SPAN Plus supports multi-track spectrum comparison (iZotope and Voxengo docs via search, not read in full) |
| L/R correlation and side/mid of processed vs reference voice | Partly | SPAN has a correlation meter; Voxengo Correlometer exists; FaustWave has a mid-side goniometer node. Overlaying them against a reference voice in one monitor: not found |
| Reproducibility claim (browser == batch) | Not found as a documented selling point | Faust's own design makes it plausible; the owner's tests (null test, shared key scheme) are the evidence |

Honest reading: the novelty is in the workflow integration and the discipline (one program text as the source of truth for both runtimes, with parameter addressing that survives rewiring). It is not in any single technique. FaustWave overlaps most of the front half. The batch and reference-matching half is where I found nothing.

## 3. Effect-chain identification and matching

Papers (peer-reviewed or arXiv, found via search; I read only abstracts or search summaries):

| Work | What it does |
|---|---|
| Lee et al., "Blind Estimation of Audio Processing Graph" (arXiv 2303.08610) | Neural encoder plus differentiable mixing console; prunes processors to a sparse graph |
| Peladeau and Peeters, ICASSP 2024 (arXiv 2310.11781) | Auto-encoder blind estimation of audio effects with differentiable DSP |
| Take et al., DAFx 2024 | Effect chain estimation plus dry signal recovery |
| Steinmetz et al., ICASSP 2021 | Differentiable mixing console of neural audio effects |
| Diff-MST (arXiv 2407.08889), "Searching for Music Mixing Graphs" (2406.01049), LLM2Fx-Tools (2512.01559) | Mixing style transfer, graph search, LLM tool calling to predict chains |
| Salimi et al., arXiv 2506.22628 | Loss functions for differentiable iterative sound matching; no code link on the abstract page |

Practical tools a hobbyist could use (license from GitHub API on 2026-10-15):

| Repo | License | Last push / stars | Use |
|---|---|---|---|
| sh-lee97/grafx | Apache-2.0 | 2026-06-29, 141 | Audio processing graphs in PyTorch. I did not confirm which processors it ships or that it covers ring mod, phaser or harmonizer |
| csteinmetz1/dasp-pytorch | Apache-2.0 | 2023-12-04, 304 | Differentiable processors (EQ, compressor, reverb etc.); stale |
| csteinmetz1/automix-toolkit | Apache-2.0 | 2024-08-28, 119 | Automix models and datasets |
| magenta/ddsp | Apache-2.0 | 2026-10-12, 3,377 | Differentiable DSP, synthesis-oriented |
| adobe-research/DeepAFx-ST | Adobe Research License (read: noncommercial research only, nonexclusive, excludes commercial use and distribution) | 2023-05-30, 413 | Style transfer of EQ/comp/reverb parameters. Not usable in a shipped tool; fine for private experiments |
| DBraun/faustax (PyPI 0.0.1, 2026-08-14) | MIT | alpha | Differentiable JAX effects compiled from Faust (EQ, comp, Freeverb, widener, panner, a vocal chain). No ring mod, comb, pitch shifter or vocoder listed |
| DawDreamer Faust-to-JAX transpile | GPL-3.0 (DawDreamer) | v0.9.0 2026-08-12 | README advertises transpiling Faust to JAX/Flax. This is the route to make the owner's own Faust differentiable, with caveats on non-differentiable parts (pitch shift, sample-and-hold) |

Assessment for this project: the owner's chain contains effects that gradient methods handle poorly (frequency shifter, ring mod, inharmonic resonators, pitch shift, vocoder). Published blind estimators target EQ, compression, reverb, distortion, so I found no open tool that estimates ring mod or phaser parameters from a reference clip. A pragmatic path that I would call plausible, not proven: fix the chain topology by ear, then fit a handful of continuous parameters against the reference spectrum and stereo statistics with a derivative-free optimiser (CMA-ES or Nelder-Mead) through DawDreamer, since the batch path already renders the same program. I did not test this. The monitor in the owner's tool is the natural scorer.

## 4. Game voice-processing context

What I found was thin:

- The only direct evidence of industry practice is a game-dialogue studio job posting (SIDE, "Voice FX Designer") saying helmeted and radio-style treatments are built with creative processing, plugins, FX chains, automation and routing. It names no tool.
- Community recipes found: an OpenGameArt "computer voice in Audacity" thread (one Delay effect: 9 ms, 30 echoes, decay 6; a comment suggests pitch down 1.5 to 2 octaves for a sinister machine voice), an Audacity forum vocoder thread, ring-modulation tutorials (Dalek-style, BBC reference, a Python port by nrlakin; one source suggests a 300 Hz carrier with 787 Hz modulator for harsh mechanical tone). These are generic.
- Wwise: I could not fetch the Wwise effect list (audiokinetic.com returned 403). I cannot confirm which built-in effects exist or whether a ring modulator is built in. Do not claim it.
- Warhammer specific: no tech-priest, servitor or vox-caster recipe thread was found. Found only a Darktide Nexus mod page restoring Medicae servitor lines and a Steam guide mentioning servitor vox units. Reddit and YouTube were not searchable from this environment.
- Rogue Trader: no AI voice-over mod for it turned up in searches. A Pathfinder: Wrath of the Righteous Nexus page asks for help from "someone skilled in AI voice generation". Rogue Trader has Steam Workshop and Unity Mod Manager support (Destructoid and Steam discussion, via search).

Demand for a browser tool for this is unproven by the evidence I found. Interest in the broader problem (robot/helmet voices) is clearly there as a long tail of Audacity-level tutorials, which suggests people want accessible, preset-driven tools more than a graph editor.

## 5. Licensing for distribution

I am reporting what the license files say. This is not legal advice. Items marked LAWYER are ones I would not decide myself.

### 5.1 What I read

| Component | License as read | Primary source |
|---|---|---|
| @grame/faustwasm 0.19.0 | `package.json` field: `LGPL-2.1`. `COPYING.txt`: "GNU Lesser General Public License ... either version 2.1 of the License, or (at your option) any later version." Copyright 2021-2026 GRAME. GitHub API shows NOASSERTION because the file is `COPYING.txt` | raw `package.json`, `COPYING.txt` |
| libfaust-wasm (folder inside faustwasm) | The Faust compiler `COPYING.txt` (v2.90.8) reads LGPL 2.1-or-later | grame-cncm/faust COPYING.txt |
| Faust standard libraries (stdfaust.lib and the other .lib files) | Header: LGPL 2.1-or-later, with "As a special exception, you may create a larger FAUST program which directly or indirectly imports this library file and still distribute the compiled code generated by the FAUST compiler, or a modified version of this compiled code, under your own copyright and license." Individual functions carry their own tags | raw `stdfaust.lib`, `compressors.lib`, `misceffects.lib`, `filters.lib` headers |
| Vue Flow (`@vue-flow/core`) | MIT, "Copyright (c) 2019-2025 webkid GmbH, Copyright (c) 2021-2025 Burak Cakmakoglu" | raw LICENSE, API (MIT) |
| DawDreamer | "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007". README: "DawDreamer is licensed under GPLv3 to make it easier to comply with all of the dependent projects", and users "must obey the licenses of" JUCE, nanobind, Libsamplerate, Rubber Band, Steinberg VST, and FAUST | raw LICENSE, README |
| Faust Playground | LGPL 2.1-or-later (COPYING.txt) | raw COPYING.txt |

### 5.2 Per-function licenses in the owner's blocks.lib

The libraries tag licenses per function, so "the stdlib is LGPL" is too coarse. Some functions are GPL. I listed every `xx.name` call in `tools/fx_lab/faust/blocks.lib` (read-only) and grepped the Faust library copy bundled in the DawDreamer venv (older than GitHub master) for declared licenses.

Functions used: an.amp_follower_ar, an.amp_follower_ud, ba.db2linear, ba.if, ba.pulse, ba.sAndH, ba.selectn, ba.take, ba.tau2pole, ba.time, co.compressor_mono, de.fdelay, ef.transpose, fi.highpass, fi.high_shelf, fi.lowpass, fi.low_shelf, fi.peak_eq, fi.resonbp, fi.tf1, fi.tf2, ma.PI, ma.SR, ma.tanh, no.noise, os.osc, os.oscp, os.phasor, os.pulsetrain, re.mono_freeverb, si.smoo, si.smooth.

- Declared "MIT-style STK-4.3": compressor_mono (via compressor_lad_mono and compression_gain_mono, also STK), tf1, tf2, resonbp, lowpass, low_shelf, peak_eq. In GitHub master, compressor_mono is `LicenseRef-STK-4.3`.
- `re.mono_freeverb`: file header LGPL with exception; a comment says this version is LGPL (with exception) and that the older example was BSD.
- `ef.transpose`: no per-function license declaration, so the file-level LGPL with exception applies (misceffects.lib header).
- Functions declared GPL in the bundled copy: the N_chan compressors, expanders and `limiter_lad_*` in compressors.lib ("GPLv3"), `vital_rev` and `kb_rom_rev1` in reverbs.lib ("GPL-3.0", confirmed in GitHub master too), `tabulateNd` (AGPL-3.0), and demos (GPL2+).
- None of those GPL functions appear in the owner's blocks.lib by my grep. This is a grep-backed statement for the current blocks.lib only. Adding a Sanfilippo limiter or the Vital reverb would change the picture. FaustMod switched from MIT to GPL-3.0-or-later in July 2026 for exactly this reason (its README: "declared GPLv3 by their authors").
- I did not check every transitive dependency (for example whether `ef.transpose`, `fi.resonbp` or `os.osc` pull in anything tagged otherwise inside the library). I only confirmed the compressor chain. Treat "all permissive" as likely, not proven.

### 5.3 What this implies

(a) Published web demo that bundles faustwasm.

- faustwasm and the embedded libfaust-wasm are LGPL-2.1-or-later. A webpage serves them to the user's browser, which is distribution. The libraries' text (the `.lib` files used by the compiler) travels inside the wasm/package too.
- The special exception frees the compiled output of a Faust program from LGPL terms. It does not free the library or compiler code itself. Do not read it as exempting the faustwasm bundle.
- Common practice that satisfies LGPL spirit: keep faustwasm as a separate, unmodified file the user could replace, ship its COPYING text and copyright notice, and link to its source. LAWYER: whether a minified single-file bundle that statically includes it satisfies the LGPL 2.1 "replace/relink" intent is genuinely debated for JavaScript. Keep it as a separate asset to avoid the question.
- Vue Flow is MIT, which requires keeping the copyright and license notice.
- cdp-web (AGPL) and FaustMod (GPL) both vendor faustwasm, which shows others do this, not that it is settled.
- The owner's own application code can use any license. Note the app plus DawDreamer interaction in (c).

(b) A GitHub repo containing generated Faust code.

- The generated `.dsp` text is the owner's own output that imports `stdfaust.lib`. It does not copy the library into the file. Under the stated exception, compiled code from such a program may be distributed under the owner's license. The `.dsp` source itself imports libraries but is not a copy of them. LAWYER if you want certainty, but the exception text was written for this case.
- If a repo vendors a copy of the `.lib` files or the Faust compiler build, keep their headers and licenses intact.

(c) Batch tool using DawDreamer.

- DawDreamer is GPL-3.0 and embeds JUCE and Faust. Running it privately to render audio for yourself imposes no obligation on the output audio. A script that `import dawdreamer` and is distributed to others is where the GPL question lives: the FSF position is that a program linked or combined with a GPL library is generally a combined work. Whether a separate Python script that imports it is one is debated. LAWYER. Safe options: license the batch tool GPL-3.0-or-later, or publish the script as documentation of how to run DawDreamer yourself, or use faustwasm/Node offline rendering (the owner already has `render_wasm.mjs`) as the redistributable batch path.
- Output audio rendered with these tools is not covered by the tools' licenses in any text I read, but the source game audio is the user's own and must not be redistributed (see section 6).

### 5.4 Other licensing flags

- DeepAFx-ST is Adobe Research License (noncommercial research). Do not bundle it.
- Faust libraries mixing GPL functions: if the owner later adds GPL-tagged functions to the blocks, a distributed app that includes them would pick up GPL obligations. Keep a notices file listing each block's library function licenses (FaustMod does this in `THIRD_PARTY_NOTICES.md`).
- AGPL projects (sonic-board, cdp-web, mod-ui) are not dependencies; do not copy their code.

## 6. Where and how to share

### 6.1 Venues and rules I could read

| Venue | Rule evidence (primary where noted) |
|---|---|
| Hacker News, Show HN | Read from news.ycombinator.com/showhn.html: "Show HN is for something you've made that other people can play with"; "Please make it easy for users to try your thing out, ideally without barriers such as signups or emails"; "Don't post quickly-generated one-offs; anybody can do that now"; "Don't post landing pages or fundraisers"; "Please don't ask friends to upvote or comment." |
| Hacker News guidelines | Read from newsguidelines.html: "Please don't put generated text in HN posts" and "Don't post generated text or AI-edited text" for comments; "Please don't use HN primarily for promotion." |
| Lobsters | Read from lobste.rs/about: self-promotion "should be less than a quarter of one's stories and comments"; invite-only, new users cannot invite for 70 days. No explicit AI rule, but spam definition covers content "created without meaningful human authorship". Low practical reach for a first post since an account is needed. |
| Faust community | Read from faust.grame.fr/community/help: Faust users mailing list (SourceForge), Faust Discord (discord.gg/qPPcXzJdmR), Audio Programmer Discord with a #faust channel, Faust GitHub Discussions. Natural first audience; GRAME also curates a "Powered by Faust" page that lists comparable tools, which is a way to get listed. I did not find a stated self-promotion rule for these. |
| Nexus Mods | Secondary only (Shacknews and others via search; the official post returned 403). Reported: on 2026-07-31 Nexus replaced one AI tag with three: AI-Generated Content (code, UI, voices, dialogue, translations, music, assets), AI Media (promo art, thumbnails, page descriptions), AI Assisted (human-led work with minor AI help). Wrong tagging can bring moderation action. The 2023 policy discouraged AI tools unless you have permission for all assets, "particularly true for AI-generated voice acting". A mod that adds generated voice over would be "AI-Generated Content". A pedalboard tool for processing voices is not itself a mod. |
| Reddit (r/audioengineering, r/DSP, r/gamedev, r/Warhammer40k, r/rogue_trader, r/WeAreTheMusicMakers) | Not verified. reddit.com cannot be fetched from this environment and a mirror failed. I have no verified text of any of these subreddits' rules. Read each subreddit's Rules page before posting; most have self-promotion limits (commonly a ratio rule) but I am not asserting any specific one. |
| KVR, Gearspace | Not researched. |

Rules about game assets: none of the venues' rules I read mention tools that process game audio. The project's own position (ship tools not audio, users extract from their own install) is the conservative stance; keep it in the post text. No Wwise or BG3 voice data should appear in a demo.

### 6.2 Comparable posts and reception (Hacker News Algolia API, read 2026-10-15)

| Post | Date | Points / comments | Read |
|---|---|---|---|
| Show HN: SOUL Language 1.0, a platform for writing and running audio code | 2021-01-20 | 119 / 81 | A new language with a platform from a notable author (JUCE). Larger ambition than this tool. |
| Show HN: Glicol, graph-oriented live coding language and DSP lib in Rust | 2022-04-07 | 58 / 29 | Browser-runnable audio DSL; a nearer comparison. Later reposts of Glicol reached 143 / 18 (2025-01-10). |
| Pedalboard: Spotify's Audio Effects Library for Python | 2021-09-08 | 256 / 50 | Big-company library; not a Show HN. Upper bound only. |
| Faust: functional programming language for real-time DSP and synthesis | 2017-12-02 | 150 / 9 | Faust itself did fine, with few comments. |
| Show HN: DAW with Modular Synth, running in a browser using stock WebAudio nodes | 2026-10-01 | 3 / 2 | Recent browser audio tool. Realistic floor. |
| Show HN: OpenMeters, a free audio metering and visualization suite | 2026-03-09 | 16 / 0 | Small tools get small attention. |
| Show HN: MegaDSP, an effects plugin for DAWs with 50 effects | 2026-07-29 | 6 / 4 | Same. |

Pattern: points scale with the author's name or a novel language and a very clean "try it now" page. Small audio utilities from unknown authors typically draw 3 to 16 points. A game-modding-specific angle has no HN comparable I found. I did not find comparable Reddit or Nexus posts, so I make no claim about their reception.

## 7. Recommendation

My reading of the evidence only.

**Worth sharing?** Yes, modestly. It is a competent specialist tool in a niche (Faust users who care about reproducible batch output, and voice-processing modders). It is not novel in its parts and it has at least one direct overlap, FaustWave, that appeared in the last year and is more polished as a general tool. Expect mild interest, not a breakout.

**To whom, in this order:**
1. Faust community (Discord, mailing list, GitHub Discussions). They know the pieces, will give the most useful technical feedback, and the "Powered by Faust" page is a listing target.
2. A game-modding audience that cares about voice-over (Rogue Trader Discord or Nexus once the mod is ready; tag AI use per Nexus policy). The post should be about the voice-processing result with audio samples, not the editor.
3. Show HN only if the demo works with no signup, loads a built-in sample voice, and the post is written by the owner by hand (HN forbids generated or AI-edited text; the project's CLAUDE.md already requires the humanizer pass for public text). Reasonable expectation is single-digit to low-double-digit points.
4. r/audioengineering and r/DSP are not verified; read their rules before use. Lobsters needs an invite and a good track record on the site.

**Form:** a static web demo (the editor needs only static hosting since compile happens in the browser), a repo with a README, three or four starter presets with a short screen capture or GIF showing: drag, wire, hear it, the monitor overlaying the reference. Show the batch reproduction as one concrete claim with a number (null-test difference in dB between browser and DawDreamer render), because that is the part nobody else shows. A demo needs a bundled test voice that is not game audio (the owner's synthetic voices or a CC0 clip).

**Minimum polish for credibility:**
- Works on a fresh browser with no setup, a loaded sample, no console errors.
- An honest "related work" line naming Faust Playground, FaustWave and FaustMod. Pretending they do not exist would be caught within minutes.
- Third-party notices file with the license table from section 5 and a link to faustwasm source.
- One verified claim of reproducibility (the null test) and the known limits from the plan stated in the UI (delay-differing parallel branches comb-filter at merge, first compile of a large graph takes a second or two).
- A short explanation of the reference-overlay monitor with one real before/after.

**Likely objections:**
- "FaustWave / Faust Playground already does this." Answer with the three items in section 2 that I could not find elsewhere, stated plainly.
- "Why not just use a DAW with plugins?" Answer: single reproducible text program, batch render, no plugin licenses.
- "AI-written?" The tool is built with AI help; disclose it in plain words. HN, Nexus and modding communities react poorly to concealed or generated prose.
- LGPL/GPL packaging questions (section 5).
- Game voice licensing and AI voice ethics will dominate any mod-level post more than the pedalboard will. Keep the pedalboard as a separate, game-agnostic announcement from the voice mod.
- Stereo in game is not yet verified (the plan's W8); do not promise it in public text.

Confidence: high that the individual techniques have prior art; medium that nothing combines the batch-reuse and reference-overlay elements (I searched, I did not find, search coverage is limited, and FaustWave's full docs were only partly read); low on audience size and on reception outside Hacker News.

## Verified vs unverified

### Verified from primary sources (fetched in this session)

- GitHub API metadata (license field, stars, pushed_at) for: grame-cncm/faustwasm, faustplayground, faustlibraries, faust, faustide; DBraun/DawDreamer (GPL-3.0, 1,327 stars, release v0.9.0 2026-08-12); bcakmakoglu/vue-flow (MIT); xyflow/xyflow (MIT); webaudiomodules/api; boourns/wam-community; deermichel/pedalboard; SoundStacks/cmajor; BespokeSynth; mod-ui; Guitarix; Ameobea/web-synth; thepacket/faustmod; RelientS/sonic-board; spotify/pedalboard; adobe-research/DeepAFx-ST; csteinmetz1/dasp-pytorch and automix-toolkit; sh-lee97/grafx; magenta/ddsp.
- faustwasm `package.json` (`LGPL-2.1`, version 0.19.0) and `COPYING.txt` header (LGPL 2.1-or-later).
- Faust Playground `COPYING.txt` header (LGPL 2.1-or-later); file listing of `src/` and `Documentation/`.
- Faust compiler `COPYING.txt` (LGPL 2.1-or-later, v2.90.8 header).
- `stdfaust.lib` exception text (three quoted fragments), and exception wording in `compressors.lib` and `misceffects.lib` headers.
- Per-function license declarations for compressor_mono (STK-4.3), vital_rev and kb_rom_rev1 (GPL-3.0) in GitHub master, and the DawDreamer-bundled library copy grep for tf1, tf2, resonbp, lowpass, low_shelf, peak_eq (STK) and the GPLv3-tagged compressor/limiter set.
- The owner's `blocks.lib` function list (read-only grep).
- Vue Flow LICENSE header (MIT, webkid GmbH and Burak Cakmakoglu); DawDreamer LICENSE title (GPL v3) and README license sentence.
- DeepAFx-ST LICENSE header ("ADOBE RESEARCH LICENSE") as summarised by the fetch tool (noncommercial research; I saw the header and the tool's summary, not the whole text).
- Faust help page channels; HN Show HN and guidelines text; Lobsters about page.
- FaustWave pages (home, docs index, first 100k characters of `llms-full.txt`) and the Faust "Powered by" page for FaustWave, nagi, FaustMod, MFP, MOD.
- HN Algolia numbers for the posts in section 6.2.
- faustax PyPI page (MIT, 0.0.1, 2026-08-14), arXiv 2506.22628 abstract page.

### Unverified, partial or from secondary summaries

- What `EquivalentFaust.ts` does is a fetch-tool summary of the file, not my line-by-line read. Whether the live Playground audio uses the fused program is unconfirmed.
- FaustWave: software license, whether the browser IDE works end to end (page showed "Loading..."), rewiring crossfade beyond the 100k characters read, reference overlay and batch render (not seen, so "not found").
- nagi: whether the graph becomes one Faust program.
- FaustMod's claim that libfaust is "LGPL-3.0" disagrees with the COPYING.txt I read (2.1-or-later). I report the primary source (2.1-or-later).
- WAM papers, Audiotool and Amped Studio capabilities, Cmajor graph and WASM claims (cmajor.dev summary), Cardinal web build, Purr Data/pd4web, Cables.gl, dsp-graph, pedalboard.js: from search summaries only.
- Differentiable/estimation papers: abstract-level only; I did not confirm code availability for most, nor that grafx or dasp-pytorch cover ring mod, phaser or harmonizer.
- Ozone and SPAN reference features: from iZotope and Voxengo docs as surfaced by search, not read in full.
- Nexus policy details: Shacknews and search summaries; the official Nexus post returned HTTP 403.
- Wwise built-in effects: not confirmed (audiokinetic.com returned 403).
- All Reddit rules: not verified (reddit.com blocked, mirror failed). KVR and Gearspace: not researched.
- Warhammer vox-caster and tech-priest recipe threads: none found; absence is limited by search tools and by Reddit/YouTube being out of reach.
- Legal interpretations in section 5.3 are readings of the license text, not advice; items flagged LAWYER need review.

## Sources

- https://github.com/grame-cncm/faustplayground and https://raw.githubusercontent.com/grame-cncm/faustplayground/master/COPYING.txt and https://raw.githubusercontent.com/grame-cncm/faustplayground/master/src/EquivalentFaust.ts
- https://github.com/grame-cncm/faustwasm, https://raw.githubusercontent.com/grame-cncm/faustwasm/master/COPYING.txt, https://raw.githubusercontent.com/grame-cncm/faustwasm/master/package.json
- https://github.com/grame-cncm/faustlibraries (stdfaust.lib, compressors.lib, misceffects.lib, reverbs.lib, filters.lib, raw files on master)
- https://raw.githubusercontent.com/grame-cncm/faust/master-dev/COPYING.txt
- https://github.com/grame-cncm/faustide
- https://faustwave.io/, https://faustwave.io/docs, https://faustwave.io/llms-full.txt, https://faustwave.io/ide/
- https://nagi.minimal-instruments.com
- https://github.com/thepacket/faustmod
- https://github.com/cdp-wasm-suite/cdp-web
- https://faust.grame.fr/community/powered-by-faust/ and https://faust.grame.fr/community/help/
- https://github.com/DBraun/DawDreamer and https://raw.githubusercontent.com/DBraun/DawDreamer/main/LICENSE
- https://raw.githubusercontent.com/bcakmakoglu/vue-flow/master/LICENSE
- https://github.com/webaudiomodules/api, https://github.com/webaudiomodules/wam-examples, https://github.com/boourns/wam-community, https://www.webaudiomodules.com/
- https://github.com/RelientS/sonic-board, https://github.com/deermichel/pedalboard, https://github.com/Ameobea/web-synth
- https://cmajor.dev, https://github.com/SoundStacks/cmajor
- https://github.com/BespokeSynth/BespokeSynth, https://github.com/mod-audio/mod-ui, https://github.com/spotify/pedalboard
- https://github.com/sh-lee97/grafx, https://github.com/csteinmetz1/dasp-pytorch, https://github.com/magenta/ddsp, https://github.com/adobe-research/DeepAFx-ST, https://raw.githubusercontent.com/adobe-research/DeepAFx-ST/main/LICENSE
- https://pypi.org/project/faustax/, https://arxiv.org/abs/2506.22628, https://arxiv.org/pdf/2303.08610, https://arxiv.org/pdf/2310.11781
- https://news.ycombinator.com/showhn.html, https://news.ycombinator.com/newsguidelines.html, https://lobste.rs/about, https://hn.algolia.com/api/v1/search (queries listed in section 6.2)
- https://www.shacknews.com/article/150216/nexus-mods-gen-ai-tagging-moderation and https://www.nexusmods.com/news/14850 (403, not read)
- https://www.izotope.com/en/learn/mix-and-master-with-reference-tracks-in-ozone.html, https://www.voxengo.com/product/span
- https://forum.hise.audio/topic/14179/lgpl-compliance-for-commercial-faust-plugins-in-hise/23 (informal)
- https://opengameart.org/forumtopic/audacity-create-a-computer-voice, https://forum.audacityteam.org/t/how-to-get-this-effect/27868, https://github.com/nrlakin/robot_voice
- https://jobs.workable.com/jobs/288e55c5-643c-478b-af24-c411ed0fbcec.md (SIDE Voice FX Designer posting, via search)
- Local files read: docs/superpowers/plans/2026-10-15-pedalboard-canvas.md, tools/fx_lab/faust/blocks.lib, tools/fx_lab/.venv-fx/lib/python3.12/site-packages/dawdreamer/faustlibraries/*.lib
