import { onBeforeUnmount, onMounted } from 'vue'
import { isTypingTarget } from '../utils/keys'
import type { WorkbenchActions } from './useWorkbenchActions'

const KEYS: Record<string, string> = { '[': 'prev', ']': 'next', s: 'save', p: 'register', e: 'edit-description', g: 'generate-design' }

/**
 * Page-level keys of the speaker workbench: [ ] previous / next speaker, S save profile, P register the pick, E edit the description,
 * G generate a live design take, Ctrl or Cmd + Enter generate takes. Letters meant for a focused candidate row (P, R, B...) are
 * handled there first and marked as handled, so they never reach this listener.
 */
export function useWorkbenchKeys(actions: WorkbenchActions) {
  function onKey(e: KeyboardEvent) {
    if (e.defaultPrevented) return
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      actions.run('generate-takes')
      return
    }
    if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || isTypingTarget(e.target)) return
    const action = KEYS[e.key.toLowerCase()]
    if (action && actions.run(action)) e.preventDefault()
  }
  onMounted(() => document.addEventListener('keydown', onKey))
  onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
}
