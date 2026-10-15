// A static stand-in for the Studio's `api` object, aliased over api/client.ts in the demo build only.
// It implements just the five pedalboard calls the store makes. Saved graphs live in localStorage.
import type { PedalboardBlocks, PedalboardGraphInfo, PedalboardSaveBody, PedalboardSaved, PedalboardStarter } from '../api/types'
import type { Graph } from '../pedalboard/types'
import type { DemoData } from '../../demo/buildData'
import { checkGraph, checkName } from './graphIo'

export const STORAGE_KEY = 'pedalboard-demo-graphs'
/** Relative so the demo works from any folder on a static host. */
export const DATA_URL = 'demo-data.json'

export class ApiRequestError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

export interface KeyValueStore { getItem(k: string): string | null; setItem(k: string, v: string): void }
interface Stored { graph: Graph; updated: string }

export interface DemoApiOptions { loadData: () => Promise<DemoData>; storage?: KeyValueStore | null; now?: () => Date }

export function createDemoApi({ loadData, storage = null, now = () => new Date() }: DemoApiOptions) {
  // Private windows can make localStorage throw or vanish; the board still works, graphs just do not persist.
  const memory = new Map<string, Stored>()
  let cached: Promise<DemoData> | null = null
  const data = () => (cached ??= loadData())

  function readAll(): Record<string, Stored> {
    try {
      const raw = storage?.getItem(STORAGE_KEY)
      const parsed: unknown = raw ? JSON.parse(raw) : {}
      if (parsed && typeof parsed === 'object') return { ...(parsed as Record<string, Stored>), ...Object.fromEntries(memory) }
    } catch { /* corrupt entry: treat as empty */ }
    return Object.fromEntries(memory)
  }
  function writeOne(name: string, entry: Stored) {
    memory.set(name, entry)
    try { storage?.setItem(STORAGE_KEY, JSON.stringify(readAll())) } catch { /* quota or blocked: kept in memory */ }
  }

  return {
    pedalboardBlocks: async (): Promise<PedalboardBlocks> => {
      const d = await data()
      return { lib: d.lib, catalog: d.catalog }
    },
    pedalboardStarters: async (): Promise<PedalboardStarter[]> => (await data()).starters,
    pedalboardGraphs: async (): Promise<PedalboardGraphInfo[]> =>
      Object.entries(readAll()).sort((a, b) => b[1].updated.localeCompare(a[1].updated)).map(([name, s]) => ({ name, updated: s.updated })),
    pedalboardGraph: async (name: string): Promise<Graph> => {
      const found = readAll()[name]
      if (!found) throw new ApiRequestError(404, `no saved graph named ${name}`)
      return found.graph
    },
    pedalboardSave: async (body: PedalboardSaveBody): Promise<PedalboardSaved> => {
      const name = checkName(body.graph?.name)
      const graph = checkGraph(body.graph, (await data()).catalog)
      writeOne(name, { graph: JSON.parse(JSON.stringify(graph)) as Graph, updated: now().toISOString() })
      return { name, dsp: `${name}.dsp`, saved: true }
    },
  }
}

async function fetchData(): Promise<DemoData> {
  const res = await fetch(DATA_URL)
  if (!res.ok) throw new Error(`Could not load ${DATA_URL} (HTTP ${res.status})`)
  return (await res.json()) as DemoData
}

function browserStorage(): KeyValueStore | null {
  try { return window.localStorage } catch { return null }
}

/** The object the store imports as `api`. Every other Studio call is absent on purpose. */
export const api = createDemoApi({ loadData: fetchData, storage: browserStorage() })
