import { describe, expect, it } from 'vitest'
import { canConnect, controlKey, paramsFor, validate } from './graph'
import { edge, fixtureCatalog as cat, graphOf, node, seriesGraph, splitMergeGraph } from './fixtures/testkit'
import type { GraphIssue } from './types'

const codes = (issues: GraphIssue[]) => issues.map((i) => i.code)

describe('controlKey', () => {
  it('joins the node id and the shortened label', () => {
    expect(controlKey('n1', 'Ring Hz')).toBe('n1_Ring_Hz')
    expect(controlKey('n2', 'Freq shift Hz (negative shifts down)')).toBe('n2_Freq_shift_Hz_negative_shifts_down')
    expect(controlKey('n3', '--odd  label--')).toBe('n3_odd_label')
  })
})

describe('validate', () => {
  it('accepts the series and split/merge graphs', () => {
    expect(validate(seriesGraph(), cat)).toEqual([])
    expect(validate(splitMergeGraph(), cat)).toEqual([])
  })
  it('flags unknown-type', () => {
    const g = seriesGraph()
    g.nodes[1].type = 'nope'
    expect(codes(validate(g, cat))).toContain('unknown-type')
  })
  it('flags bad-id and duplicate-id', () => {
    const g = seriesGraph()
    g.nodes[1].id = '2bad'
    g.nodes[2].id = 'n1'
    const c = codes(validate(g, cat))
    expect(c).toContain('bad-id')
    expect(c).toContain('duplicate-id')
  })
  it('flags bad-edge for a dangling source or target', () => {
    const g = seriesGraph()
    g.edges.push(edge('ghost', 'n2', 0, 'x'), edge('n1', 'ghost', 0, 'y'))
    expect(codes(validate(g, cat)).filter((c) => c === 'bad-edge')).toHaveLength(2)
  })
  it('flags bad-port', () => {
    const g = seriesGraph()
    g.edges[0].targetPort = 3
    expect(codes(validate(g, cat))).toContain('bad-port')
  })
  it('flags port-taken', () => {
    const g = seriesGraph()
    g.edges.push(edge('n1', 'n3', 0, 'dup'))
    expect(codes(validate(g, cat))).toContain('port-taken')
  })
  it('flags missing-input', () => {
    const g = splitMergeGraph()
    g.edges = g.edges.filter((e) => e.id !== 'n3_n4_1')
    const issues = validate(g, cat)
    expect(issues.find((i) => i.code === 'missing-input')?.nodeId).toBe('n4')
  })
  it('flags cycle', () => {
    const g = graphOf(
      [node('n1', 'input'), node('n2', 'gain'), node('n3', 'gain'), node('n4', 'output')],
      [edge('n1', 'n2'), edge('n2', 'n3'), edge('n3', 'n2'), edge('n3', 'n4')],
    )
    expect(codes(validate(g, cat))).toContain('cycle')
  })
  it('flags no-path for an unreachable node', () => {
    const g = seriesGraph()
    g.nodes.push(node('n9', 'gain'))
    g.edges.push(edge('n9', 'n9', 0, 'self'))
    const c = codes(validate(g, cat))
    expect(c).toContain('cycle')
    const g2 = seriesGraph()
    g2.nodes.push(node('n9', 'mix2'))
    g2.edges.push(edge('n2', 'n9', 0, 'p0'), edge('n2', 'n9', 1, 'p1'))
    const issues = validate(g2, cat)
    expect(issues.find((i) => i.code === 'no-path')?.nodeId).toBe('n9')
  })
  it('requires exactly one input and one output', () => {
    const g = graphOf([node('n1', 'input'), node('n2', 'gain')], [edge('n1', 'n2')])
    expect(codes(validate(g, cat))).toContain('no-path')
  })
})

describe('canConnect', () => {
  const base = () =>
    graphOf([node('n1', 'input'), node('n2', 'gain'), node('n3', 'mix2'), node('n4', 'output')], [edge('n1', 'n2')])
  it('allows a normal wire, and a free second port of a mix', () => {
    expect(canConnect(base(), cat, edge('n2', 'n3', 0))).toEqual({ ok: true })
    expect(canConnect(base(), cat, edge('n1', 'n3', 1))).toEqual({ ok: true })
  })
  it('refuses a self loop', () => {
    expect(canConnect(base(), cat, edge('n2', 'n2'))).toMatchObject({ ok: false })
  })
  it('refuses a wire that closes a loop', () => {
    const g = base()
    g.edges.push(edge('n2', 'n3', 0))
    const r = canConnect(g, cat, edge('n3', 'n2'))
    expect(r).toMatchObject({ ok: false })
  })
  it('refuses a second wire into a taken port', () => {
    expect(canConnect(base(), cat, edge('n3', 'n2', 0, 'new'))).toMatchObject({ ok: false, reason: expect.stringContaining('already') })
  })
  it('refuses a bad port index', () => {
    expect(canConnect(base(), cat, edge('n2', 'n3', 2))).toMatchObject({ ok: false })
    expect(canConnect(base(), cat, edge('n2', 'n3', -1))).toMatchObject({ ok: false })
  })
  it('refuses the output node as a source and the input node as a target', () => {
    expect(canConnect(base(), cat, edge('n4', 'n3', 0))).toMatchObject({ ok: false })
    expect(canConnect(base(), cat, edge('n2', 'n1', 0))).toMatchObject({ ok: false })
  })
  it('refuses missing nodes', () => {
    expect(canConnect(base(), cat, edge('n2', 'zz'))).toMatchObject({ ok: false })
  })
  it('lets an existing edge be re-checked against itself', () => {
    const g = base()
    expect(canConnect(g, cat, g.edges[0])).toEqual({ ok: true })
  })
})

describe('paramsFor', () => {
  it('fills defaults, maps stomp to 1/0 and uses stored params', () => {
    const g = seriesGraph()
    g.nodes[1].on = false
    g.nodes[2].params = { 'Gain dB': 6 }
    expect(paramsFor(g, cat)).toEqual({
      n2_Gain_dB: 0,
      n2_on: 0,
      n3_Gain_dB: 6,
      n3_on: 1,
      n4_Output_dB: 0,
    })
  })
  it('keys two instances of one block apart', () => {
    const keys = Object.keys(paramsFor(splitMergeGraph(), cat))
    expect(keys).toContain('n2_Gain_dB')
    expect(keys).toContain('n3_Gain_dB')
    expect(new Set(keys).size).toBe(keys.length)
  })
  it('ignores params for labels the block does not have', () => {
    const g = seriesGraph()
    g.nodes[1].params = { Bogus: 3 }
    expect(Object.keys(paramsFor(g, cat))).not.toContain('n2_Bogus')
  })
})
