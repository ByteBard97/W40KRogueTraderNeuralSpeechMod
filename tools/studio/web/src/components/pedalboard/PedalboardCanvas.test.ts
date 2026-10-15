import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { chainGraph, realCatalog } from '../../test-utils/pedalboardCatalog'
import { usePedalboardStore } from '../../stores/pedalboard'

const flowApi = vi.hoisted(() => ({ setEdges: vi.fn(), fitView: vi.fn() }))

// Vue Flow needs real layout to run, so it is replaced by a stub that only forwards the canvas's props and events.
vi.mock('@vue-flow/core', async (orig) => ({
  ...(await orig<typeof import('@vue-flow/core')>()),
  VueFlow: { name: 'VueFlow', props: ['nodes', 'isValidConnection'], emits: ['connect', 'connect-end', 'node-drag-stop', 'selection-change'], template: '<div class="vf" />' },
  useVueFlow: () => ({ screenToFlowCoordinate: (p: { x: number; y: number }) => ({ x: p.x, y: p.y }), fitView: flowApi.fitView, setEdges: flowApi.setEdges }),
}))
vi.mock('@vue-flow/background', () => ({ Background: { template: '<i />' } }))
vi.mock('@vue-flow/controls', () => ({ Controls: { template: '<i />' } }))

import PedalboardCanvas from './PedalboardCanvas.vue'
import { PALETTE_MIME } from './paletteDrag'

function setup() {
  const store = usePedalboardStore()
  store.catalog = realCatalog
  store.loadGraph(chainGraph())
  const w = mount(PedalboardCanvas, { attachTo: document.body })
  const flow = w.findComponent({ name: 'VueFlow' })
  return { store, w, flow }
}

describe('PedalboardCanvas', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    flowApi.setEdges.mockClear()
    flowApi.fitView.mockClear()
  })

  it('turns the store graph into pedal and structural nodes with typed handles', () => {
    const { flow, w } = setup()
    const nodes = flow.props('nodes') as Array<{ id: string; type: string; deletable: boolean }>
    expect(nodes.map((n) => [n.id, n.type, n.deletable])).toEqual([['input', 'structural', false], ['highpass1', 'pedal', true], ['output', 'structural', false]])
    w.unmount()
  })

  it('gives Vue Flow the edges after the nodes, not as a prop (it drops edges whose nodes are not in its state yet), and re-fits when a graph is loaded', async () => {
    const { flow, store, w } = setup()
    expect(flow.props()).not.toHaveProperty('edges')
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    const last = flowApi.setEdges.mock.calls.at(-1)?.[0] as Array<{ source: string; target: string; sourceHandle: string; targetHandle: string }>
    expect(last[0]).toMatchObject({ source: 'input', target: 'highpass1', sourceHandle: 'out0', targetHandle: 'in0' })
    const calls = flowApi.setEdges.mock.calls.length
    store.addNode('lowpass', 0, 0)
    store.connect({ source: 'highpass1', target: 'lowpass1', sourcePort: 0, targetPort: 0 })
    await w.vm.$nextTick()
    await w.vm.$nextTick()
    expect(flowApi.setEdges.mock.calls.length).toBeGreaterThan(calls)
    expect((flowApi.setEdges.mock.calls.at(-1)?.[0] as unknown[]).length).toBeGreaterThan(last.length)
    flowApi.fitView.mockClear()
    vi.useFakeTimers()
    store.newGraph()
    await w.vm.$nextTick()
    expect(flowApi.fitView).not.toHaveBeenCalled()      // the fit waits for Vue Flow to measure the new nodes
    vi.advanceTimersByTime(400)
    expect(flowApi.fitView).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
    w.unmount()
  })

  it('saves the node position when a drag stops', () => {
    const { flow, store, w } = setup()
    flow.vm.$emit('node-drag-stop', { node: { id: 'highpass1', position: { x: 41.6, y: 7.2 } } })
    expect(store.nodeOf('highpass1')).toMatchObject({ x: 42, y: 7 })
    w.unmount()
  })

  it('routes a new connection through the store and shows the reason when refused', async () => {
    const { flow, store, w } = setup()
    store.addNode('lowpass', 0, 0)
    flow.vm.$emit('connect', { source: 'highpass1', target: 'lowpass1', sourceHandle: 'out0', targetHandle: 'in0' })
    expect(store.graph.edges.some((e) => e.source === 'highpass1' && e.target === 'lowpass1')).toBe(true)
    flow.vm.$emit('connect', { source: 'input', target: 'lowpass1', sourceHandle: 'out0', targetHandle: 'in0' })
    await w.vm.$nextTick()
    expect(w.get('[data-testid="refusal"]').text()).toBe('that input already has a wire')
    w.unmount()
  })

  it('asks the store, without changing it, while a cable is dragged', () => {
    const { flow, store, w } = setup()
    const isValid = flow.props('isValidConnection') as (c: unknown) => boolean
    const before = store.graph.edges.length
    expect(isValid({ source: 'input', target: 'highpass1', sourceHandle: 'out0', targetHandle: 'in0' })).toBe(true)      // this wire is already in the graph: Vue Flow runs the check on existing edges too, they must pass or none is drawn
    expect(isValid({ source: 'output', target: 'highpass1', sourceHandle: 'out0', targetHandle: 'in0' })).toBe(false)    // a different source into a taken input is refused
    expect(store.graph.edges).toHaveLength(before)
    w.unmount()
  })

  it('adds a pedal at the drop point', async () => {
    const { store, w } = setup()
    const drop = new Event('drop', { bubbles: true }) as unknown as DragEvent
    Object.assign(drop, { clientX: 500, clientY: 300, dataTransfer: { getData: (t: string) => (t === PALETTE_MIME ? 'echo' : '') } })
    w.get('[data-testid="canvas"]').element.dispatchEvent(drop)
    expect(store.nodeOf('echo1')).toBeTruthy()
    expect(store.selection).toEqual(['echo1'])
    w.unmount()
  })

  it('adds a pedal at the viewport centre on request', () => {
    const { store, w } = setup()
    ;(w.vm as unknown as { addAtCenter: (t: string) => void }).addAtCenter('echo')
    expect(store.nodeOf('echo1')).toBeTruthy()
    w.unmount()
  })

  it('Delete removes selected pedals and wires but never Input or Output', () => {
    const { flow, store, w } = setup()
    flow.vm.$emit('selection-change', { nodes: [{ id: 'input' }, { id: 'highpass1' }, { id: 'output' }], edges: [] })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete' }))
    expect(store.graph.nodes.map((n) => n.id)).toEqual(['input', 'output'])
    store.loadGraph(chainGraph())
    flow.vm.$emit('selection-change', { nodes: [], edges: [{ id: 'e1' }] })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace' }))
    expect(store.graph.edges.map((e) => e.id)).toEqual(['e2'])
    flow.vm.$emit('selection-change', { nodes: [{ id: 'input' }], edges: [] })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete' }))
    expect(store.graph.nodes).toHaveLength(3)
    w.unmount()
  })
})
