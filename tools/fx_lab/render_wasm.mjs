// Render a Faust .dsp over a raw float32 mono file with the same FaustWasm engine the FX Lab page uses (no browser needed).
// Used by null_test.py to check that the browser runtime and DawDreamer agree.
//   node render_wasm.mjs <file.dsp> <in.f32> <sampleRate> <params.json> <out.f32> [tailSeconds]
// params.json is {shortname: value}; anything not listed keeps its default (checkboxes default to 1 = on, like the page).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const { FaustCompiler, FaustMonoDspGenerator, LibFaust, instantiateFaustModuleFromFile } =
  await import(pathToFileURL(path.join(here, 'vendor/faustwasm/index.js')).href);

const [dspFile, inFile, srArg, paramsFile, outFile, tailArg] = process.argv.slice(2);
const sr = +srArg, tail = Math.round((+tailArg || 0) * sr);
const lib = path.join(here, 'vendor/libfaust-wasm');
const mod = await instantiateFaustModuleFromFile(path.join(lib, 'libfaust-wasm.js'), path.join(lib, 'libfaust-wasm.data'), path.join(lib, 'libfaust-wasm.wasm'));
const gen = new FaustMonoDspGenerator();
await gen.compile(new FaustCompiler(new LibFaust(mod)), 'fx', fs.readFileSync(dspFile, 'utf8'), '-ftz 2');
const proc = await gen.createOfflineProcessor(sr, 128);

const params = JSON.parse(fs.readFileSync(paramsFile, 'utf8'));
for (const d of proc.getDescriptors()) {
  const v = d.shortname in params ? params[d.shortname] : (d.type === 'checkbox' ? 1 : +d.init);
  proc.setParamValue(d.address, v);
}
const raw = fs.readFileSync(inFile);
const x = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const padded = new Float32Array(x.length + tail); padded.set(x);
const [y] = proc.render([padded], padded.length);
fs.writeFileSync(outFile, Buffer.from(y.buffer, y.byteOffset, y.byteLength));
