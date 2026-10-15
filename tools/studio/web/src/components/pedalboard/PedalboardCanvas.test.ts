import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { chainGraph, realCatalog } from '../../test-utils/pedalboardCatalog'
import { usePedalboardStore } from '../../stores/pedalboard'

const flowApi = vi.hoisted(() => ({ setEdges: vi.fn(), fitView: vi.fn(), nodes: null as unknown as { value: unknown[] }, edges: null as unknown as { value: unknown[] } }))
// Selection reaches the canvas as reactive lists of the selected nodes and edges (Vue Flow 1.48 has no selection-change event).
const select = async (nodes: unknown[], edges: unknown[] = []) => {
  flowApi.nodes.value = nodes
  flowApi.edges.value = edges
  await nextTick()
}

// Vue Flow needs real layout to run, so it is replaced by a stub that only forwards the canvas's props and events.
vi.mock('@vue-flow/core', async (orig) => {
  const { ref } = await import('vue')
  flowApi.nodes = ref<unknown[]>([])
  flowApi.edges = ref<unknown[]>([])
  return {
  ...(await orig<typeof import('@vue-flow/core')>()),
  VueFlow: { name: 'VueFlow', props: ['nodes', 'isValidConnection'], emits: ['connect', 'connect-end', 'node-drag-stop'], template: '<div class="vf" />' },
  useVueFlow: () => ({ screenToFlowCoordinate: (p: { x: number; y: number }) => ({ x: p.x, y: p.y }), fitView: flowApi.fitView, setEdges: flowApi.setEdges, getSelectedNodes: flowApi.nodes, getSelectedEdges: flowApi.edges }),
  }
})
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

  it('Delete removes selected pedals and wires but never Input or Output', async () => {
    const { flow, store, w } = setup()
    await select([{ id: 'input' }, { id: 'highpass1' }, { id: 'output' }], [])
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete' }))
    expect(store.graph.nodes.map((n) => n.id)).toEqual(['input', 'output'])
    store.loadGraph(chainGraph())
    await select([], [{ id: 'e1' }])
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace' }))
    expect(store.graph.edges.map((e) => e.id)).toEqual(['e2'])
    await select([{ id: 'input' }], [])
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete' }))
    expect(store.graph.nodes).toHaveLength(3)
    w.unmount()
  })

  it('re-reporting the same selected wire does not make Vue Flow re-apply the wires (that looped until the stack overflowed in the browser)', async () => {
    const { w } = setup()
    await select([], [{ id: 'e1' }])
    await w.vm.$nextTick()
    const calls = flowApi.setEdges.mock.calls.length
    await select([], [{ id: 'e1' }])
    await select([], [{ id: 'e1' }])
    expect(flowApi.setEdges.mock.calls.length).toBe(calls)
    await select([], [{ id: 'e2' }])
    await w.vm.$nextTick()
    expect(flowApi.setEdges.mock.calls.length).toBeGreaterThan(calls)      // a real change still updates the wires' selected look
    w.unmount()
  })

  it('deletes a multi-selection as one undoable step', async () => {
    const { flow, store, w } = setup()
    store.addNode('lowpass', 0, 0)
    store.loadGraph({ ...chainGraph(), nodes: [...chainGraph().nodes, { id: 'lowpass1', type: 'lowpass', x: 0, y: 0 }] })
    await select([{ id: 'highpass1' }, { id: 'lowpass1' }], [])
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete' }))
    expect(store.graph.nodes.map((n) => n.id)).toEqual(['input', 'output'])
    expect(store.undoCount).toBe(1)
    w.unmount()
  })

  it('saves every node of a group drag', () => {
    const { flow, store, w } = setup()
    store.addNode('lowpass', 0, 0)
    flow.vm.$emit('node-drag-stop', { node: { id: 'highpass1' }, nodes: [{ id: 'highpass1', position: { x: 11, y: 12 } }, { id: 'lowpass1', position: { x: 21, y: 22 } }] })
    expect(store.nodeOf('lowpass1')).toMatchObject({ x: 21, y: 22 })
    expect(store.nodeOf('highpass1')).toMatchObject({ x: 11, y: 12 })
    w.unmount()
  })

  it('undoes and copies from the keyboard, but not while a text field has focus', () => {
    const { store, w } = setup()
    store.addNode('lowpass', 0, 0)
    store.select(['lowpass1'])
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd', ctrlKey: true }))
    expect(store.nodeOf('lowpass2')).toBeTruthy()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true }))
    expect(store.nodeOf('lowpass2')).toBeUndefined()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, shiftKey: true }))
    expect(store.nodeOf('lowpass2')).toBeTruthy()
    const field = document.createElement('input')
    field.type = 'text'
    document.body.appendChild(field)
    field.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true }))
    expect(store.nodeOf('lowpass2')).toBeTruthy()
    field.remove()
    w.unmount()
  })

  it('shows the empty hint only while just Input and Output are on the board', async () => {
    const { store, w } = setup()
    expect(w.find('[data-testid="empty-hint"]').exists()).toBe(false)
    store.newGraph()
    await w.vm.$nextTick()
    expect(w.get('[data-testid="empty-hint"]').text()).toContain('Drag a pedal from the left')
    w.unmount()
  })

  it('Tidy and Bypass all drive the store and the note says the change is not saved', async () => {
    const { store, w } = setup()
    const fit = store.fitRev
    await w.get('[data-testid="tidy-btn"]').trigger('click')
    expect(store.fitRev).toBe(fit + 1)
    await w.get('[data-testid="bypass-all"]').trigger('click')
    expect(store.bypassAll).toBe(true)
    expect(w.get('[data-testid="audition-note"]').text()).toContain('not saved')
    expect(w.get('[data-testid="bypass-all"]').attributes('aria-pressed')).toBe('true')
    w.unmount()
  })

  it('draws a pedal muted while Solo silences it', async () => {
    const { flow, store, w } = setup()
    store.addNode('lowpass', 0, 0)
    store.toggleSolo('lowpass1')
    await w.vm.$nextTick()
    const nodes = flow.props('nodes') as Array<{ id: string; data: { muted?: boolean; solo?: boolean } }>
    expect(nodes.find((n) => n.id === 'highpass1')?.data).toMatchObject({ muted: true, solo: false })
    expect(nodes.find((n) => n.id === 'lowpass1')?.data).toMatchObject({ muted: false, solo: true })
    w.unmount()
  })
})
