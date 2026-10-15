// Plain-language wording for validation issues, so the owner never reads node ids or error codes.
import { blockFor, OUTPUT_TYPE } from './graph'
import type { Catalog, Graph, GraphIssue } from './types'

function labelOf(graph: Graph, catalog: Catalog, nodeId: string | undefined): string {
  const node = graph.nodes.find((n) => n.id === nodeId)
  if (!node) return 'A pedal'
  return blockFor(catalog, node.type)?.name ?? node.type
}

export function describeIssue(issue: GraphIssue, graph: Graph, catalog: Catalog): string {
  const node = graph.nodes.find((n) => n.id === issue.nodeId)
  const who = labelOf(graph, catalog, issue.nodeId)
  switch (issue.code) {
    case 'missing-input':
      return node?.type === OUTPUT_TYPE ? 'The Output is not connected' : `${who} has an input with nothing plugged in`
    case 'no-path':
      return node ? `${who} is not on a path from the Input to the Output` : 'The graph needs one Input and one Output'
    case 'cycle':
      return 'The wires form a loop. Remove one wire to break it'
    case 'port-taken':
      return `${who} has two wires into one input`
    default:
      return issue.message
  }
}
