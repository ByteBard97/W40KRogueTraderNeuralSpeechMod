import { onBeforeUnmount, onMounted, readonly, ref, shallowRef } from 'vue'

export interface ShortcutItem {
  label: string
  /** Each entry is one keycap, e.g. ['J', 'K'] or ['Shift', '←']. */
  keys: string[]
}
export interface ShortcutGroup {
  title: string
  items: ShortcutItem[]
}
export interface ShortcutSet {
  /** Shown as "Shortcuts · {title}". */
  title: string
  groups: ShortcutGroup[]
}

/** Shortcuts every page has, listed after the page's own groups. */
export const GLOBAL_SHORTCUTS: ShortcutGroup = {
  title: 'Everywhere',
  items: [
    { label: 'Play / pause', keys: ['Space'] },
    { label: 'Seek 1 s back / forward', keys: ['←', '→'] },
    { label: 'Seek 5 s', keys: ['Shift', '←', '→'] },
    { label: 'Previous / next clip', keys: [',', '.'] },
    { label: 'Loop', keys: ['L'] },
    { label: 'Speed down / up', keys: ['[', ']'] },
    { label: 'This overlay', keys: ['?'] },
  ],
}

// shallow: the cleanup below compares by identity with the object the page registered
const page = shallowRef<ShortcutSet | null>(null)
const open = ref(false)

/** Register the current page's shortcut list for the overlay. Call from a page's setup; it clears on unmount. */
export function useShortcuts(set: ShortcutSet) {
  onMounted(() => (page.value = set))
  onBeforeUnmount(() => {
    if (page.value === set) page.value = null
  })
}

export function useShortcutOverlay() {
  return {
    page: readonly(page),
    open,
    show: () => (open.value = true),
    hide: () => (open.value = false),
    toggle: () => (open.value = !open.value),
  }
}
