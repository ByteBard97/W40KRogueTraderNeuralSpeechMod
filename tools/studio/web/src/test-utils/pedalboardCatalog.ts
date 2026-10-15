// The real block catalog and library from tools/fx_lab/faust, read with fs so tests do not depend on vite's fs rules.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Catalog, Graph } from '../pedalboard/types'

const FAUST_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', 'fx_lab', 'faust')
export const realCatalog = JSON.parse(readFileSync(join(FAUST_DIR, 'catalog.json'), 'utf8')) as Catalog
export const realLib = readFileSync(join(FAUST_DIR, 'blocks.lib'), 'utf8')

/** input -> highpass -> output, ids as the store makes them. */
export const chainGraph = (): Graph => ({
  version: 1,
  name: '',
  nodes: [
    { id: 'input', type: 'input', x: 0, y: 0 },
    { id: 'highpass1', type: 'highpass', x: 200, y: 0 },
    { id: 'output', type: 'output', x: 400, y: 0, params: {} },
  ],
  edges: [
    { id: 'e1', source: 'input', target: 'highpass1', targetPort: 0 },
    { id: 'e2', source: 'highpass1', target: 'output', targetPort: 0 },
  ],
})
