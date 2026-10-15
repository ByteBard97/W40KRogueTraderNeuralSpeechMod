import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { realCatalog } from '../../test-utils/pedalboardCatalog'
import type { GraphNode } from '../../pedalboard/types'
import PedalNode from './PedalNode.vue'
import StructuralNode from './StructuralNode.vue'

const block = (id: string) => realCatalog.blocks.find((b) => b.id === id)!
const stubs = { Handle: { props: ['id', 'type'], template: '<i class="handle" :data-id="id" :data-type="type" />' } }

function pedal(type: string, over: Partial<GraphNode> = {}) {
  const node: GraphNode = { id: `${type}1`, type, x: 0, y: 0, ...over }
  return mount(PedalNode, { props: { id: node.id, data: { node, block: block(type) } }, global: { stubs } })
}

describe('PedalNode', () => {
  it('renders one row per control except the stomp, and shows the stomp', () => {
    const b = block('metal')
    const w = pedal('metal')
    const rows = b.controls.filter((c) => c.label !== b.stomp)
    expect(w.findAll('.row')).toHaveLength(rows.length)
    expect(w.find('[data-testid="stomp-metal1"]').exists()).toBe(true)
    expect(w.find('[data-testid="pedal-metal1"]').exists()).toBe(true)
    expect(w.text()).toContain(b.name)
  })

  it('emits stomp with the opposite state and shows bypassed when off', async () => {
    const w = pedal('metal')
    await w.get('[data-testid="stomp-metal1"]').trigger('click')
    expect(w.emitted('stomp')![0]).toEqual([false])
    const off = pedal('metal', { on: false })
    expect(off.get('[data-testid="stomp-metal1"]').attributes('aria-checked')).toBe('false')
    await off.get('[data-testid="stomp-metal1"]').trigger('click')
    expect(off.emitted('stomp')![0]).toEqual([true])
  })

  it('emits param with the label when a number is typed', async () => {
    const b = block('metal')
    const c = b.controls.find((x) => x.label !== b.stomp)!
    const w = pedal('metal')
    const input = w.get(`[data-testid^="ctrl-metal1-"]`)
    await input.setValue(String(c.max))
    expect(w.emitted('param')![0]).toEqual([c.label, c.max])
  })

  it('uses the stored value over init, and double click resets to init', async () => {
    const b = block('metal')
    const c = b.controls.find((x) => x.label !== b.stomp && x.type === 'hslider')!
    const w = pedal('metal', { params: { [c.label]: c.max } })
    const row = w.findAll('.row').find((r) => r.text().includes(c.label))!
    expect(Number((row.get('input[type="number"]').element as HTMLInputElement).value)).toBe(c.max)
    await row.trigger('dblclick')
    expect(w.emitted('param')![0]).toEqual([c.label, c.init])
  })

  it('adjusts on mouse wheel', async () => {
    const b = block('metal')
    const c = b.controls.find((x) => x.label !== b.stomp && x.type === 'hslider')!
    const w = pedal('metal')
    const row = w.findAll('.row').find((r) => r.text().includes(c.label))!
    await row.trigger('wheel', { deltaY: -100 })
    const [label, v] = w.emitted('param')![0] as [string, number]
    expect(label).toBe(c.label)
    expect(v).toBeGreaterThan(c.init)
  })

  it('marks sliders so Vue Flow leaves them alone', () => {
    const w = pedal('metal')
    expect(w.find('.row.nodrag.nowheel').exists()).toBe(true)
    expect(w.find('.stomp.nodrag').exists()).toBe(true)
  })

  it('hides the controls when collapsed', async () => {
    const w = pedal('metal')
    await w.get('[data-testid="collapse-metal1"]').trigger('click')
    expect(w.findAll('.row')).toHaveLength(0)
  })

  it('gives Mix one labelled input per wire and no stomp', () => {
    const w = pedal('mix3')
    expect(w.findAll('.handle[data-type="target"]')).toHaveLength(3)
    expect(w.findAll('.port-label').map((l) => l.text())).toEqual(['A', 'B', 'C'])
    expect(w.find('[data-testid="stomp-mix31"]').exists()).toBe(false)
    expect(w.findAll('.handle[data-type="source"]')).toHaveLength(1)
  })

  it('a normal pedal has one input and one output handle', () => {
    const w = pedal('metal')
    expect(w.findAll('.handle[data-type="target"]')).toHaveLength(1)
    expect(w.findAll('.handle[data-type="source"]')).toHaveLength(1)
  })
})

describe('StructuralNode', () => {
  const mk = (type: string) => {
    const node: GraphNode = { id: type, type, x: 0, y: 0 }
    return mount(StructuralNode, { props: { id: type, data: { node, block: block(type) } }, global: { stubs } })
  }
  it('Input has only an output handle and no controls', () => {
    const w = mk('input')
    expect(w.findAll('.handle[data-type="source"]')).toHaveLength(1)
    expect(w.findAll('.handle[data-type="target"]')).toHaveLength(0)
    expect(w.findAll('.row')).toHaveLength(0)
  })
  it('Output has an input handle and its controls, and emits param', async () => {
    const w = mk('output')
    expect(w.findAll('.handle[data-type="target"]')).toHaveLength(1)
    expect(w.findAll('.row').length).toBe(block('output').controls.length)
    await w.get('[data-testid="ctrl-output-Output_dB"]').setValue('-6')
    expect(w.emitted('param')![0]).toEqual(['Output dB', -6])
  })
})
