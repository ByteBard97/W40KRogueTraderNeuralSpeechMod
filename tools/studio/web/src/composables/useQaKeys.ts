import { onBeforeUnmount, onMounted } from 'vue'
import { keyAction, type QaAction } from '../utils/qaKeys'

const TYPING_TAGS = ['INPUT', 'SELECT', 'TEXTAREA']

/** Binds Render QA shortcuts on mount, leaves typing fields alone, unbinds on unmount. */
export function useQaKeys(handle: (action: QaAction) => void) {
  function onKey(e: KeyboardEvent) {
    const t = e.target as HTMLElement | null
    if (t && (TYPING_TAGS.includes(t.tagName) || t.isContentEditable)) return
    if (e.ctrlKey || e.metaKey || e.altKey) return
    const action = keyAction(e.key)
    if (!action) return
    e.preventDefault()
    handle(action)
  }
  onMounted(() => document.addEventListener('keydown', onKey))
  onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
}
