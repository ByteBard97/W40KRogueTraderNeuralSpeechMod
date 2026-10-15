// Build faust/catalog.json from faust/blocks.lib: compile each block alone with FaustWasm and read its controls.
//   node build_catalog.mjs [--out path] [--check]      (--check: exit 1 if the file on disk differs from a fresh build)
// The metadata table below is the only hand-written part; the controls (label, type, init, min, max, step) come from the compiler.
// Labels come from the descriptor's `label`, never `shortname` (Faust shortens that to the shortest unique suffix).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const { FaustCompiler, FaustMonoDspGenerator, LibFaust, instantiateFaustModuleFromFile } =
  await import(pathToFileURL(path.join(here, 'vendor/faustwasm/index.js')).href);

const E = (id, name, category, description, stomp, extra = {}) =>
  ({ id, name, category, description, kind: 'effect', stomp, inputs: 1, outputs: 1, stereoNative: false, ...extra });
const S = { stereoNative: true };
const BLOCKS = [
  E('highpass', 'Highpass', 'Tone', 'Cuts everything below a cutoff frequency; 0 turns it off.', 'Highpass on'),
  E('lowpass', 'Lowpass', 'Tone', 'Cuts everything above a cutoff frequency; 0 turns it off.', 'Lowpass on'),
  E('deesser', 'De-esser', 'Tone', 'Compresses only the harsh sibilant band so s and t sounds stay tame before other effects exaggerate them.', 'De-ess on'),
  E('eq', 'EQ', 'Tone', 'Three peaking bands and a high shelf to shape the tone.', 'EQ on'),
  E('lowshelf', 'Low shelf', 'Tone', 'Boosts or cuts everything below 200 Hz.', 'Low shelf on'),
  E('compressor', 'Compressor', 'Tone', 'Evens out loud and quiet parts with threshold, ratio, attack, release and makeup gain.', 'Compressor on'),
  E('pitch', 'Pitch shift', 'Pitch & voice', 'Shifts the whole voice up or down by semitones and adds about 20 ms of delay.', 'Pitch on'),
  E('harmonizer', 'Harmonizer', 'Pitch & voice', 'Adds up to two pitch-shifted copies of the voice for a doubled, choir-like sound.', 'Harmonizer on'),
  E('freqshift', 'Frequency shifter', 'Pitch & voice', 'Moves every partial by the same number of Hz, which turns a natural voice inharmonic and eerie.', 'Freq shift on'),
  E('vocoder', 'Vocoder', 'Pitch & voice', 'Replaces the voice with a monotone buzz that keeps the words, for a robot or cyborg sound.', 'Vocoder on'),
  E('wowflutter', 'Wow and flutter', 'Pitch & voice', 'Slow and fast pitch wobble like a worn tape or an unstable vox link.', 'Wow flutter on'),
  E('resonator', 'Resonator', 'Metal', 'Adds four fixed resonant peaks, like the ring of a small metal box, grille or helmet.', 'Resonator on'),
  E('metal', 'Metal bank', 'Metal', 'Six narrow ringing resonances laid out like a struck metal bar, so the voice sounds like it hits metal.', 'Metal on'),
  E('comb', 'Comb', 'Metal', 'A short feedback delay that gives a hollow pipe or robotic flange tone.', 'Comb on'),
  E('ringmod', 'Ring mod', 'Metal', 'Multiplies the voice by a sine wave for a classic metallic robot voice.', 'Ring on'),
  E('drive', 'Drive', 'Metal', 'Soft saturation that adds grit and harmonics.', 'Drive on'),
  E('bitcrush', 'Bitcrusher', 'Metal', 'Lowers the bit depth and sample hold rate for a crunchy digital sound.', 'Crush on'),
  E('tremolo', 'Tremolo', 'Modulation', 'Wobbles the volume at a steady rate.', 'Tremolo on'),
  E('chorus', 'Chorus', 'Modulation', 'Mixes in two slightly detuned, modulated copies for a thicker voice.', 'Chorus on'),
  E('phaser', 'Phaser', 'Modulation', 'Sweeps moving notches through the sound with an allpass chain.', 'Phaser on'),
  E('echo', 'Echo', 'Space', 'Repeating delay with feedback and a mix control.', 'Echo on'),
  E('reverb', 'Reverb', 'Space', 'Adds the sound of a room with size and damping.', 'Reverb on'),
  E('static', 'Static', 'Space', 'Band-limited radio hiss that only sounds while the character speaks.', 'Static on'),
  E('dropout', 'Dropout', 'Space', 'Randomly mutes short pieces of the signal like a failing vox-caster.', 'Dropout on'),
  E('autopan', 'Auto pan', 'Stereo', 'Sweeps the voice between left and right with an LFO.', 'Auto pan on', S),
  E('stereochorus', 'Stereo chorus', 'Stereo', 'A chorus whose left and right sides move out of step for width.', 'Stereo chorus on', S),
  E('stereophaser', 'Stereo phaser', 'Stereo', 'A phaser whose left and right sweeps are offset for a swirling stereo image.', 'Stereo phaser on', S),
  E('bassspread', 'Bass spread', 'Stereo', 'Delays the low band differently in each ear while the highs stay put.', 'Bass spread on', S),
  { id: 'mix2', name: 'Mix 2', category: 'Routing', description: 'Sums two stereo wires with a level for each.', kind: 'structural', stomp: null, inputs: 2, outputs: 1, stereoNative: true },
  { id: 'mix3', name: 'Mix 3', category: 'Routing', description: 'Sums three stereo wires with a level for each.', kind: 'structural', stomp: null, inputs: 3, outputs: 1, stereoNative: true },
  { id: 'mix4', name: 'Mix 4', category: 'Routing', description: 'Sums four stereo wires with a level for each.', kind: 'structural', stomp: null, inputs: 4, outputs: 1, stereoNative: true },
  { id: 'output', name: 'Output', category: 'Output', description: 'Final output level, limiter and hard clip on both channels.', kind: 'structural', stomp: null, inputs: 1, outputs: 1, stereoNative: true },
];
// The input node is only a graph endpoint: the mono clip duplicated to left and right. It has no Faust box.
const INPUT = { id: 'input', name: 'Input', category: 'Routing', description: 'The raw voice clip, sent to both channels.', kind: 'structural', stomp: null, inputs: 0, outputs: 1, node: null, stereoNative: false, controls: [] };

const args = process.argv.slice(2);
const outIdx = args.indexOf('--out');
const outFile = outIdx >= 0 ? args[outIdx + 1] : path.join(here, 'faust/catalog.json');
const check = args.includes('--check');
const libText = fs.readFileSync(path.join(here, 'faust/blocks.lib'), 'utf8');

const lib = path.join(here, 'vendor/libfaust-wasm');
const mod = await instantiateFaustModuleFromFile(path.join(lib, 'libfaust-wasm.js'), path.join(lib, 'libfaust-wasm.data'), path.join(lib, 'libfaust-wasm.wasm'));
const compiler = new FaustCompiler(new LibFaust(mod));

async function controlsOf(b) {
  const code = `${libText}\nprocess = vgroup("fx", _ <: si.bus(${2 * b.inputs}) : vgroup("n1", node_${b.id}));\n`;
  const gen = new FaustMonoDspGenerator();
  await gen.compile(compiler, 'fx', code, '-ftz 2');
  const proc = await gen.createOfflineProcessor(24000, 128);
  // A Faust checkbox has no init/min/max/step in its descriptor (NaN, written as null); give it the values the plan fixes: on by default, 0..1, step 1.
  return proc.getDescriptors().map(d => d.type === 'checkbox'
    ? { label: d.label, type: d.type, init: 1, min: 0, max: 1, step: 1 }
    : { label: d.label, type: d.type, init: +d.init, min: +d.min, max: +d.max, step: +d.step });
}

const blocks = [INPUT];
for (const b of BLOCKS) blocks.push({ ...b, node: `node_${b.id}`, controls: await controlsOf(b) });
const order = ['id', 'name', 'category', 'description', 'kind', 'stomp', 'inputs', 'outputs', 'node', 'stereoNative', 'controls'];
const text = JSON.stringify({ version: 1, blocks: blocks.map(b => Object.fromEntries(order.map(k => [k, b[k]]))) }, null, 2) + '\n';

if (check) {
  const same = fs.existsSync(outFile) && fs.readFileSync(outFile, 'utf8') === text;
  console.log(same ? 'catalog.json is up to date' : 'catalog.json is out of date');
  process.exit(same ? 0 : 1);
}
fs.writeFileSync(outFile, text);
console.log(`wrote ${outFile} (${blocks.length} blocks)`);
