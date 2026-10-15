import { describe, expect, it } from 'vitest'
import { generate } from './generate'
import { GraphError } from './types'
import { edge, fixtureCatalog as cat, fixtureLib as lib, graphOf, node, seriesGraph, skipGraph, splitMergeGraph } from './fixtures/testkit'

const processPart = (code: string) => code.slice(code.indexOf('process ='))
const routes = (code: string) => code.match(/route\([^\n]*/g) ?? []

describe('generate', () => {
  it('series: no route is needed', () => {
    const { code } = generate(seriesGraph(), cat, lib)
    expect(routes(code)).toEqual([])
    expect(processPart(code)).toMatch(/process = vgroup\("fx",/)
    expect(code.indexOf('vgroup("n2"')).toBeLessThan(code.indexOf('vgroup("n3"'))
  })
  it('starts with the stdfaust import exactly once, even if the lib has one', () => {
    const { code } = generate(seriesGraph(), cat, lib)
    expect(code.startsWith('import("stdfaust.lib");')).toBe(true)
    expect(code.match(/import\("stdfaust\.lib"\)/g)).toHaveLength(1)
    expect(code).toContain('node_gain = par(i, 2, chan)')
  })
  it('split and merge: duplicates the input, then merges through the mix', () => {
    const { code } = generate(splitMergeGraph(), cat, lib)
    expect(routes(code)).toEqual(['route(2, 4, (1,1), (2,2), (1,3), (2,4))'])
    expect(processPart(code)).toContain('vgroup("n4", node_mix2)')
  })
  it('skip connection: the jumping wire rides along as si.bus(2)', () => {
    const { code } = generate(skipGraph(), cat, lib)
    expect(routes(code)[0]).toBe('route(2, 4, (1,1), (2,2), (1,3), (2,4))')
    expect(processPart(code)).toContain('si.bus(2)')
    // layer 2: mix takes the gain wire (channels 1,2) then the passthrough (3,4): identity, so no second route
    expect(routes(code)).toHaveLength(1)
  })
  it('fan-out: one source feeds several inputs from the same channels', () => {
    const g = graphOf(
      [node('n1', 'input'), node('n2', 'gain'), node('n3', 'mix2'), node('n4', 'output')],
      [edge('n1', 'n2'), edge('n2', 'n3', 0), edge('n2', 'n3', 1), edge('n3', 'n4')],
    )
    const { code } = generate(g, cat, lib)
    expect(routes(code)).toEqual(['route(2, 4, (1,1), (2,2), (1,3), (2,4))'])
  })
  it('two instances of one block get distinct control keys', () => {
    const { controls } = generate(splitMergeGraph(), cat, lib)
    const gains = controls.filter((c) => c.label === 'Gain dB')
    expect(gains.map((c) => c.key)).toEqual(['n2_Gain_dB', 'n3_Gain_dB'])
    expect(controls.map((c) => c.key)).toContain('n5_Output_dB')
    expect(controls[0]).toMatchObject({ nodeId: 'n2', type: 'hslider', init: 0, min: -24, max: 24, step: 0.1 })
  })
  it('throws GraphError with the issue list for an invalid graph', () => {
    const g = seriesGraph()
    g.edges.pop()
    try {
      generate(g, cat, lib)
      expect.unreachable()
    } catch (e) {
      expect(e).toBeInstanceOf(GraphError)
      expect((e as GraphError).issues.map((i) => i.code)).toContain('missing-input')
    }
  })
  it('input straight to output needs no route and no pass-through', () => {
    const g = graphOf([node('n1', 'input'), node('n2', 'output')], [edge('n1', 'n2')])
    const { code } = generate(g, cat, lib)
    expect(routes(code)).toEqual([])
    expect(processPart(code)).toContain('vgroup("n2", node_output)')
  })
  it('golden: series', async () => {
    await expect(processPart(generate(seriesGraph(), cat, lib).code)).toMatchFileSnapshot('./fixtures/golden/series.txt')
  })
  it('golden: split and merge', async () => {
    await expect(processPart(generate(splitMergeGraph(), cat, lib).code)).toMatchFileSnapshot('./fixtures/golden/split_merge.txt')
  })
  it('golden: skip connection', async () => {
    await expect(processPart(generate(skipGraph(), cat, lib).code)).toMatchFileSnapshot('./fixtures/golden/skip.txt')
  })
})
