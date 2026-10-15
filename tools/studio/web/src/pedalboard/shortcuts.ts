// Keyboard shortcuts for the editor, kept apart from the canvas so they can be tested without a browser.
import type { usePedalboardStore } from '../stores/pedalboard'

type Store = ReturnType<typeof usePedalboardStore>

const NON_TEXT_INPUTS = new Set(['range', 'checkbox', 'radio', 'button', 'submit'])

/**
 * True when the key press belongs to a text field (its own undo, copy and paste must work).
 * Range sliders do not count: a knob keeps focus after a drag, and Ctrl+Z must still undo that drag.
 */
export function isTextEntry(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false
  if (t.isContentEditable || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT') return true
  return t.tagName === 'INPUT' && !NON_TEXT_INPUTS.has((t as HTMLInputElement).type)
}

/** Handles Ctrl/Cmd+Z, +Shift+Z, +Y, +C, +V, +D. Returns true when the event was consumed. */
export function handleShortcut(e: KeyboardEvent, store: Store): boolean {
  if (!(e.ctrlKey || e.metaKey) || e.altKey || isTextEntry(e.target)) return false
  const key = e.key.toLowerCase()
  if (key === 'z') (e.shiftKey ? store.redo : store.undo)()
  else if (key === 'y') store.redo()
  else if (key === 'c') store.copySelection()
  else if (key === 'v') store.paste()
  else if (key === 'd') store.duplicateSelection()
  else return false
  e.preventDefault()
  return true
}
