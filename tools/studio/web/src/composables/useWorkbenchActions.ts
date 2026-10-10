import { inject, onBeforeUnmount, onMounted, provide, type InjectionKey } from 'vue'

/** Named page actions (save, register, generate...) that components register and the page's shortcut handler runs. */
export interface WorkbenchActions {
  register(name: string, fn: () => void): () => void
  run(name: string): boolean
}

const KEY: InjectionKey<WorkbenchActions> = Symbol('workbenchActions')

export function provideWorkbenchActions(): WorkbenchActions {
  const map = new Map<string, () => void>()
  const actions: WorkbenchActions = {
    register(name, fn) {
      map.set(name, fn)
      return () => map.get(name) === fn && map.delete(name)
    },
    run(name) {
      const fn = map.get(name)
      fn?.()
      return !!fn
    },
  }
  provide(KEY, actions)
  return actions
}

/** Register `fn` under `name` while the calling component is mounted. A no-op outside a workbench page. */
export function useWorkbenchAction(name: string, fn: () => void) {
  const actions = inject(KEY, null)
  let off: (() => void) | null = null
  onMounted(() => { off = actions?.register(name, fn) ?? null })
  onBeforeUnmount(() => off?.())
}
