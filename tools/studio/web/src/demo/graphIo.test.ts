import { describe, expect, it } from 'vitest'
import { readDemoData } from '../../demo/buildData'
import { resolve } from 'node:path'
import { checkName, fileStem, GraphFileError, parseGraphFile, serializeGraph } from './graphIo'

const data = readDemoData(resolve(__dirname, '../../../../fx_lab'))
const good = data.starters[0].graph

describe('graph files', () => {
  it('export then import returns the same graph', () => {
    expect(parseGraphFile(serializeGraph(good), data.catalog)).toEqual(good)
  })
  it('every bundled starter passes import validation', () => {
    for (const s of data.starters) expect(() => parseGraphFile(serializeGraph(s.graph), data.catalog), s.slug).not.toThrow()
  })
  const cases: Array<[string, string, RegExp]> = [
    ['not JSON', '{oops', /not valid JSON/],
    ['an array', '[]', /expected a JSON object/],
    ['wrong version', JSON.stringify({ ...good, version: 2 }), /Unsupported graph version 2/],
    ['no nodes', JSON.stringify({ version: 1, name: 'x', edges: [] }), /"nodes" list/],
    ['unknown pedal', JSON.stringify({ ...good, nodes: [...good.nodes, { id: 'z', type: 'flux-capacitor', x: 0, y: 0 }] }), /unknown pedal type "flux-capacitor"/],
    ['duplicate ids', JSON.stringify({ ...good, nodes: [good.nodes[0], good.nodes[0]] }), /share the id/],
    ['bad coordinates', JSON.stringify({ ...good, nodes: [{ id: 'a', type: 'input', x: 'left', y: 0 }] }), /numeric x and y/],
    ['dangling wire', JSON.stringify({ ...good, edges: [{ id: 'e', source: 'input', target: 'ghost', targetPort: 0 }] }), /not in the file/],
    ['bad param', JSON.stringify({ ...good, nodes: [{ id: 'input', type: 'input', x: 0, y: 0, params: { a: 'loud' } }] }), /not numbers/],
  ]
  it.each(cases)('rejects %s with a readable message', (_n, text, rx) => {
    expect(() => parseGraphFile(text, data.catalog)).toThrow(GraphFileError)
    expect(() => parseGraphFile(text, data.catalog)).toThrow(rx)
  })
  it('checks names and builds safe file names', () => {
    expect(checkName('ok_name-1')).toBe('ok_name-1')
    expect(() => checkName('')).toThrow(GraphFileError)
    expect(() => checkName('a/b')).toThrow(GraphFileError)
    expect(fileStem(' My chain! ')).toBe('My-chain')
    expect(fileStem('???')).toBe('pedalboard-graph')
  })
})
