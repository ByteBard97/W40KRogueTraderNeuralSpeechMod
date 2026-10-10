import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { api } from '../api/client'
import type { FxBackup, FxDiff, FxLabels, FxPresetInfo, FxPreview, FxRestored, FxUsage, FxWritten } from '../api/types'
import { useNavCountsStore } from './navCounts'

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))
const same = (a: string[] = [], b: string[] = []) => a.length === b.length && a.every((x, i) => x === b[i])
const copy = (l: FxLabels): FxLabels => Object.fromEntries(Object.entries(l).map(([k, v]) => [k, [...v]]))

export const useFxStore = defineStore('fx', () => {
  const library = ref<FxPresetInfo[]>([])
  /** The label map as saved on disk. */
  const labels = ref<FxLabels>({})
  /** The label map being edited. */
  const draft = ref<FxLabels>({})
  const preview = ref<FxPreview | null>(null)
  const written = ref<FxWritten | null>(null)
  const usage = ref<FxUsage | null>(null)
  const diff = ref<FxDiff | null>(null)
  const backups = ref<FxBackup[]>([])
  const loaded = ref(false)
  const writing = ref(false)
  const error = ref<string | null>(null)

  const labelNames = computed(() => Object.keys(labels.value))
  const dirtyLabels = computed(() => labelNames.value.filter((l) => !same(draft.value[l], labels.value[l])))
  const dirtyCount = computed(() => dirtyLabels.value.length)
  const isDirty = (label: string) => dirtyLabels.value.includes(label)

  const nav = useNavCountsStore()
  watch(dirtyCount, (n) => (nav.fxUnsaved = n), { immediate: true })

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    try {
      return await fn()
    } catch (e) {
      error.value = msg(e)
      return undefined
    }
  }
  /** For routes the server may not have yet: failure leaves the value empty and shows nothing. */
  async function soft<T>(fn: () => Promise<T>): Promise<T | null> {
    try {
      return await fn()
    } catch {
      return null
    }
  }

  async function refreshDerived() {
    const [u, d, b] = await Promise.all([soft(api.fxUsage), soft(api.fxDiff), soft(api.fxBackups)])
    usage.value = u
    diff.value = d
    backups.value = b ?? []
    if (!d) preview.value = await soft(api.fxPreview)
  }
  async function load() {
    error.value = null
    library.value = (await run(api.fxLibrary)) ?? []
    const saved = (await run(api.fxLabels)) ?? {}
    // Edits in progress survive a reload (a preset saved in the FX Lab refreshes the library only).
    const keep = dirtyCount.value > 0
    labels.value = saved
    if (!keep) draft.value = copy(saved)
    await refreshDerived()
    loaded.value = true
  }
  async function reloadLibrary() {
    const lib = await run(api.fxLibrary)
    if (lib) library.value = lib
  }

  function add(label: string, name: string) {
    const chain = (draft.value[label] ??= [])
    if (name && !chain.includes(name)) chain.push(name)
  }
  function remove(label: string, i: number) {
    draft.value[label]?.splice(i, 1)
  }
  function move(label: string, from: number, to: number) {
    const chain = draft.value[label]
    if (!chain || to < 0 || to >= chain.length || from === to) return
    const [x] = chain.splice(from, 1)
    chain.splice(to, 0, x)
  }
  function discard() {
    draft.value = copy(labels.value)
  }

  async function saveLabels(next: FxLabels = draft.value) {
    error.value = null
    const saved = await run(() => api.fxSaveLabels(next))
    if (saved) {
      labels.value = saved
      draft.value = copy(saved)
      preview.value = null
    }
    return saved
  }
  async function loadPreview() {
    error.value = null
    preview.value = (await run(api.fxPreview)) ?? null
    written.value = null
  }
  /** "Write map": save the edited labels (the server backs up the old file), then expand them into assignments.json. */
  async function writeMap(): Promise<FxWritten | undefined> {
    writing.value = true
    error.value = null
    try {
      if (dirtyCount.value && !(await saveLabels())) return undefined
      const w = await run(api.fxWrite)
      written.value = w ?? null
      if (w) await refreshDerived()
      return w
    } finally {
      writing.value = false
    }
  }
  async function restore(backup: string): Promise<FxRestored | undefined> {
    error.value = null
    const r = await run(() => api.fxRestore(backup))
    if (r) await load()
    return r
  }
  return {
    library, labels, draft, preview, written, usage, diff, backups, loaded, writing, error,
    labelNames, dirtyLabels, dirtyCount, isDirty,
    load, reloadLibrary, add, remove, move, discard, saveLabels, loadPreview, writeMap, restore,
  }
})
