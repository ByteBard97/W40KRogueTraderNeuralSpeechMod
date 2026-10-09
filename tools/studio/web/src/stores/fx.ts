import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { FxLabels, FxPresetInfo, FxPreview, FxWritten } from '../api/types'

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export const useFxStore = defineStore('fx', () => {
  const library = ref<FxPresetInfo[]>([])
  const labels = ref<FxLabels>({})
  const preview = ref<FxPreview | null>(null)
  const written = ref<FxWritten | null>(null)
  const error = ref<string | null>(null)

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    error.value = null
    try {
      return await fn()
    } catch (e) {
      error.value = msg(e)
      return undefined
    }
  }
  async function load() {
    library.value = (await run(api.fxLibrary)) ?? []
    labels.value = (await run(api.fxLabels)) ?? {}
  }
  async function saveLabels(next: FxLabels) {
    const saved = await run(() => api.fxSaveLabels(next))
    if (saved) {
      labels.value = saved
      preview.value = null
    }
  }
  async function loadPreview() {
    preview.value = (await run(api.fxPreview)) ?? null
    written.value = null
  }
  async function write() {
    written.value = (await run(api.fxWrite)) ?? null
  }
  return { library, labels, preview, written, error, load, saveLabels, loadPreview, write }
})
