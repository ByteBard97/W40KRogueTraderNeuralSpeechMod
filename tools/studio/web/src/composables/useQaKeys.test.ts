import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useQaKeys } from './useQaKeys'

function host(handle: (a: string) => void) {
  return mount(defineComponent({ setup() { useQaKeys(handle); return () => h('div', [h('input'), h('select'), h('button')]) } }), { attachTo: document.body })
}
const press = (key: string, target: Element | Document = document) => target.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))

describe('useQaKeys', () => {
  it('calls the handler for mapped keys', () => {
    const fn = vi.fn()
    const w = host(fn)
    press('j')
    press('g')
    press('q')
    expect(fn.mock.calls).toEqual([['next'], ['good']])
    w.unmount()
  })

  it('ignores keys typed into inputs and selects', () => {
    const fn = vi.fn()
    const w = host(fn)
    press('j', w.find('input').element)
    press('b', w.find('select').element)
    expect(fn).not.toHaveBeenCalled()
    w.unmount()
  })

  it('ignores ctrl combinations and stops listening after unmount', () => {
    const fn = vi.fn()
    const w = host(fn)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'j', ctrlKey: true }))
    expect(fn).not.toHaveBeenCalled()
    w.unmount()
    press('j')
    expect(fn).not.toHaveBeenCalled()
  })
})
