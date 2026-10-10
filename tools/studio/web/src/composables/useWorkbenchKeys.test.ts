import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { provideWorkbenchActions, useWorkbenchAction } from './useWorkbenchActions'
import { useWorkbenchKeys } from './useWorkbenchKeys'

const fns = { save: vi.fn(), next: vi.fn(), edit: vi.fn(), takes: vi.fn() }
const Child = defineComponent({ setup() { useWorkbenchAction('save', fns.save); useWorkbenchAction('next', fns.next); useWorkbenchAction('edit-description', fns.edit); useWorkbenchAction('generate-takes', fns.takes); return () => h('input') } })
const Page = defineComponent({ setup() { useWorkbenchKeys(provideWorkbenchActions()); return () => h(Child) } })
const press = (init: KeyboardEventInit, target: EventTarget = document) => {
  const ev = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init })
  target.dispatchEvent(ev)
  return ev
}

describe('workbench keys', () => {
  it('runs the registered action for S, ] and E, and Ctrl+Enter generates takes', () => {
    const w = mount(Page, { attachTo: document.body })
    press({ key: 's' })
    press({ key: ']' })
    press({ key: 'e' })
    press({ key: 'Enter', ctrlKey: true })
    expect([fns.save, fns.next, fns.edit, fns.takes].map((f) => f.mock.calls.length)).toEqual([1, 1, 1, 1])
    w.unmount()
  })

  it('ignores keys while typing, with modifiers, or already handled', () => {
    const w = mount(Page, { attachTo: document.body })
    fns.save.mockClear()
    press({ key: 's' }, w.find('input').element)
    press({ key: 's', shiftKey: true })
    const handled = new KeyboardEvent('keydown', { key: 's', cancelable: true, bubbles: true })
    handled.preventDefault()
    document.dispatchEvent(handled)
    expect(fns.save).not.toHaveBeenCalled()
    w.unmount()
  })

  it('does not swallow a key whose action is not registered (P without a design)', () => {
    const w = mount(Page, { attachTo: document.body })
    expect(press({ key: 'p' }).defaultPrevented).toBe(false)
    w.unmount()
  })

  it('stops listening after unmount', () => {
    const w = mount(Page, { attachTo: document.body })
    w.unmount()
    fns.save.mockClear()
    press({ key: 's' })
    expect(fns.save).not.toHaveBeenCalled()
  })
})
