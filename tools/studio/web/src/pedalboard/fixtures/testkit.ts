// Helpers shared by the pedalboard tests: fixture loading and tiny graph builders.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Catalog, Graph, GraphEdge, GraphNode } from '../types'

export const FIXTURE_DIR = dirname(fileURLToPath(import.meta.url))
export const FIXTURE_LIB_PATH = join(FIXTURE_DIR, 'blocks.lib')
export const FIXTURE_CATALOG_PATH = join(FIXTURE_DIR, 'catalog.json')
export const fixtureLib = readFileSync(FIXTURE_LIB_PATH, 'utf8')
export const fixtureCatalog = JSON.parse(readFileSync(FIXTURE_CATALOG_PATH, 'utf8')) as Catalog

export function node(id: string, type: string, extra: Partial<GraphNode> = {}): GraphNode {
  return { id, type, x: 0, y: 0, ...extra }
}

export function edge(source: string, target: string, targetPort = 0, id = `${source}_${target}_${targetPort}`): GraphEdge {
  return { id, source, target, targetPort }
}

export function graphOf(nodes: GraphNode[], edges: GraphEdge[]): Graph {
  return { version: 1, name: 'test', nodes, edges }
}

// in -> n2 gain -> n3 gain -> out
export const seriesGraph = (): Graph =>
  graphOf(
    [node('n1', 'input'), node('n2', 'gain'), node('n3', 'gain'), node('n4', 'output')],
    [edge('n1', 'n2'), edge('n2', 'n3'), edge('n3', 'n4')],
  )

// in fans out to two gains that meet in a mix2
export const splitMergeGraph = (): Graph =>
  graphOf(
    [node('n1', 'input'), node('n2', 'gain'), node('n3', 'gain'), node('n4', 'mix2'), node('n5', 'output')],
    [edge('n1', 'n2'), edge('n1', 'n3'), edge('n2', 'n4', 0), edge('n3', 'n4', 1), edge('n4', 'n5')],
  )

// the input also jumps straight over a gain into the mix
export const skipGraph = (): Graph =>
  graphOf(
    [node('n1', 'input'), node('n2', 'gain'), node('n3', 'mix2'), node('n4', 'output')],
    [edge('n1', 'n2'), edge('n2', 'n3', 0), edge('n1', 'n3', 1), edge('n3', 'n4')],
  )
