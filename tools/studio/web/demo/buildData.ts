// Reads the real Faust block library, catalog and starting points, so the static demo never carries its own copies.
// Mirrors server/studio_server/starters.py: same fields, same category order, malformed files skipped.
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import type { PedalboardStarter } from '../src/api/types'
import type { Catalog } from '../src/pedalboard/types'

export interface DemoData { lib: string; catalog: Catalog; starters: PedalboardStarter[] }

const CATEGORY_ORDER = ['Clean', 'Machine', 'Vox', 'Helmet', 'Ethereal', 'Monstrous', 'Space', 'Rogue Trader', 'Test']

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

export function readStarters(dir: string): PedalboardStarter[] {
  if (!existsSync(dir)) return []
  const found: PedalboardStarter[] = []
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.json')).sort()) {
    try {
      const d: unknown = JSON.parse(readFileSync(join(dir, file), 'utf8'))
      if (!isObject(d) || !isObject(d.graph) || typeof d.name !== 'string' || typeof d.category !== 'string') continue
      found.push({ slug: file.replace(/\.json$/, ''), name: d.name, description: typeof d.description === 'string' ? d.description : '', category: d.category, graph: d.graph as unknown as PedalboardStarter['graph'] })
    } catch { /* one bad file must not take the whole menu down */ }
  }
  const rank = (c: string) => { const i = CATEGORY_ORDER.indexOf(c); return i < 0 ? CATEGORY_ORDER.length : i }
  return found.sort((a, b) => rank(a.category) - rank(b.category) || a.name.toLowerCase().localeCompare(b.name.toLowerCase()) || a.slug.localeCompare(b.slug))
}

/** `fxLab` is tools/fx_lab. */
export function readDemoData(fxLab: string): DemoData {
  return {
    lib: readFileSync(join(fxLab, 'faust', 'blocks.lib'), 'utf8'),
    catalog: JSON.parse(readFileSync(join(fxLab, 'faust', 'catalog.json'), 'utf8')) as Catalog,
    starters: readStarters(join(fxLab, 'starters')),
  }
}
