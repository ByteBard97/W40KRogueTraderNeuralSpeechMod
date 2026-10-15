import { describe, expect, it, vi } from 'vitest'
import { handleShortcut, isTextEntry } from './shortcuts'

const fakeStore = () => ({ undo: vi.fn(), redo: vi.fn(), copySelection: vi.fn(), paste: vi.fn(), duplicateSelection: vi.fn() })
const press = (key: string, init: KeyboardEventInit = {}, target?: HTMLElement) => {
  const e = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init })
  if (target) Object.defineProperty(e, 'target', { value: target })
  return e
}

describe('editor shortcuts', () => {
  it('maps undo, redo (both spellings), copy, paste and duplicate for Ctrl and Cmd', () => {
    const s = fakeStore()
    expect(handleShortcut(press('z', { ctrlKey: true }), s as never)).toBe(true)
    handleShortcut(press('Z', { metaKey: true, shiftKey: true }), s as never)
    handleShortcut(press('y', { ctrlKey: true }), s as never)
    handleShortcut(press('c', { ctrlKey: true }), s as never)
    handleShortcut(press('v', { metaKey: true }), s as never)
    handleShortcut(press('d', { ctrlKey: true }), s as never)
    expect([s.undo, s.redo, s.copySelection, s.paste, s.duplicateSelection].map((f) => f.mock.calls.length)).toEqual([1, 2, 1, 1, 1])
  })

  it('claims the event so the browser does not also bookmark or reload', () => {
    const e = press('d', { ctrlKey: true })
    handleShortcut(e, fakeStore() as never)
    expect(e.defaultPrevented).toBe(true)
  })

  it('ignores plain keys and unknown chords', () => {
    const s = fakeStore()
    expect(handleShortcut(press('z'), s as never)).toBe(false)
    expect(handleShortcut(press('q', { ctrlKey: true }), s as never)).toBe(false)
    expect(s.undo).not.toHaveBeenCalled()
  })

  it('is ignored while typing in a text field but not on a knob', () => {
    const s = fakeStore()
    const text = document.createElement('input')
    text.type = 'text'
    const num = document.createElement('input')
    num.type = 'number'
    const area = document.createElement('textarea')
    const range = document.createElement('input')
    range.type = 'range'
    expect([text, num, area].every(isTextEntry)).toBe(true)
    expect(isTextEntry(range)).toBe(false)
    expect(handleShortcut(press('z', { ctrlKey: true }, text), s as never)).toBe(false)
    expect(handleShortcut(press('v', { ctrlKey: true }, area), s as never)).toBe(false)
    expect(s.undo).not.toHaveBeenCalled()
    expect(handleShortcut(press('z', { ctrlKey: true }, range), s as never)).toBe(true)
  })
})
