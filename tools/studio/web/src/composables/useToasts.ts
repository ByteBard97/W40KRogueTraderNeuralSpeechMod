import { readonly, ref } from 'vue'

export type ToastKind = 'ok' | 'err'
export interface ToastAction {
  label: string
  /** Keycap shown on the button and bound while the toast is visible. */
  key?: string
  run: () => void
}
export interface Toast {
  id: number
  kind: ToastKind
  message: string
  action?: ToastAction
}

export const TOAST_MS = 6000
export const TOAST_ERROR_MS = 10000

const toasts = ref<Toast[]>([])
let nextId = 1

function dismiss(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

function push(kind: ToastKind, message: string, action?: ToastAction): number {
  const id = nextId++
  toasts.value = [...toasts.value, { id, kind, message, action }]
  setTimeout(() => dismiss(id), kind === 'err' ? TOAST_ERROR_MS : TOAST_MS)
  return id
}

/** App-wide toasts. `undo` replaces a modal confirm: do the thing, then offer to take it back. */
export function useToasts() {
  return {
    toasts: readonly(toasts),
    dismiss,
    ok: (message: string) => push('ok', message),
    error: (message: string, retry?: () => void) => push('err', message, retry ? { label: 'Retry', run: retry } : undefined),
    undo: (message: string, undo: () => void) => push('ok', message, { label: 'Undo', key: 'Z', run: undo }),
    clear: () => (toasts.value = []),
  }
}
