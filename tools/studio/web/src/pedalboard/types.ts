// Shared shapes for the pedalboard graph, the block catalog and the generator output.
// The graph and catalog schemas are fixed by docs/superpowers/plans/2026-10-15-pedalboard-canvas.md.

export type ControlType = 'hslider' | 'vslider' | 'nentry' | 'checkbox' | 'button'

export interface CatalogControl {
  label: string
  type: ControlType
  init: number
  min: number
  max: number
  step: number
}

export interface CatalogBlock {
  id: string
  name: string
  category: string
  description: string
  kind: 'effect' | 'structural'
  // Label of the on/off checkbox; null for blocks that cannot be bypassed.
  stomp: string | null
  // Counts of STEREO wires. The output node is the exception: 1 in, 0 out here, but its Faust box is 2 in 2 out.
  inputs: number
  outputs: number
  node: string
  stereoNative: boolean
  controls: CatalogControl[]
}

export interface Catalog {
  version: number
  blocks: CatalogBlock[]
}

export interface GraphNode {
  id: string
  type: string
  x: number
  y: number
  on?: boolean
  // Keyed by control label (as in the catalog); a missing label means the control's init.
  params?: Record<string, number>
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  targetPort: number
  // Which stereo output of the source feeds this wire. Every v1 block has one output, so it defaults to 0.
  sourcePort?: number
}

export interface Graph {
  version: number
  name: string
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export type IssueCode =
  | 'unknown-type'
  | 'cycle'
  | 'port-taken'
  | 'bad-port'
  | 'missing-input'
  | 'no-path'
  | 'duplicate-id'
  | 'bad-id'
  | 'bad-edge'

export interface GraphIssue {
  code: IssueCode
  message: string
  nodeId?: string
  edgeId?: string
}

// A control as the generated program exposes it. `key` is the flat parameter key used by every runtime.
export interface Control {
  key: string
  nodeId: string
  label: string
  type: ControlType
  init: number
  min: number
  max: number
  step: number
}

export interface Generated {
  code: string
  controls: Control[]
}

export type CanConnectResult = { ok: true } | { ok: false; reason: string }

export class GraphError extends Error {
  readonly issues: GraphIssue[]
  constructor(issues: GraphIssue[]) {
    super(`invalid graph: ${issues.map((i) => `${i.code}: ${i.message}`).join('; ')}`)
    this.name = 'GraphError'
    this.issues = issues
  }
}
