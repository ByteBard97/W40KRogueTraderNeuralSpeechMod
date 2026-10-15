// Generate several graphs in one process (npx startup costs seconds per call):
//   cd tools/studio/web && npx vite-node ../../fx_lab/gen_batch.ts -- <graph.json> [<graph.json> ...]
// Prints {"<path>": {code, controls, params} | {error: [...issues]}} as JSON. Used by migrate_scenarios.py and tests/test_starters.py.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { generate, paramsFor } from '../studio/web/src/pedalboard/generate'
import { GraphError } from '../studio/web/src/pedalboard/types'
import type { Catalog, Graph } from '../studio/web/src/pedalboard/types'

const FAUST = resolve(__dirname, 'faust')
const catalog = JSON.parse(readFileSync(resolve(FAUST, 'catalog.json'), 'utf8')) as Catalog
const lib = readFileSync(resolve(FAUST, 'blocks.lib'), 'utf8')
const out: Record<string, unknown> = {}
for (const p of process.argv.slice(2).filter((a) => a !== '--')) {
  try {
    const graph = JSON.parse(readFileSync(p, 'utf8')) as Graph
    const { code, controls } = generate(graph, catalog, lib)
    out[p] = { code, controls, params: paramsFor(graph, catalog) }
  } catch (e) {
    out[p] = { error: e instanceof GraphError ? e.issues : String(e) }
  }
}
process.stdout.write(JSON.stringify(out))
