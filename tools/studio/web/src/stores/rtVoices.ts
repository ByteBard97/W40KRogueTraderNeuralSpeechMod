import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Bg3Voice, LabelDef, LabelProgress, LabelValue } from '../api/types'
import { labelsComplete } from '../utils/castVoices'

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** The Rogue Trader voices that have game audio, and the owner's labels on them. Same shape as the BG3 voices in the casting store, so one page labels both. */
export const useRtVoicesStore = defineStore('rtVoices', () => {
  const voices = ref<Bg3Voice[]>([])
  const schema = ref<LabelDef[]>([])
  const progress = ref<LabelProgress | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)

  async function load() {
    loading.value = true
    error.value = null
    try {
      const p = await api.rtVoices()
      voices.value = p.voices
      schema.value = p.schema
      progress.value = p.progress
    } catch (e) {
      error.value = msg(e)
    } finally {
      loading.value = false
    }
  }

  async function setLabel(slug: string, key: string, value: LabelValue | null) {
    const v = voices.value.find((x) => x.slug === slug)
    if (!v) return
    const before = { mine: { ...v.mine }, labels: { ...v.labels }, complete: v.complete }
    const empty = value === null || value === '' || (Array.isArray(value) && !value.length)
    v.mine = { ...v.mine, [key]: empty ? undefined : value }
    v.labels = { ...v.labels, [key]: empty ? undefined : value }
    v.complete = labelsComplete(v.mine, schema.value)
    try {
      v.mine = await api.rtVoiceLabelSet(slug, key, empty ? null : value)
      v.labels = v.mine
      progress.value = (await api.rtVoices()).progress
    } catch (e) {
      Object.assign(v, before)
      error.value = msg(e)
    }
  }

  return { voices, schema, progress, error, loading, load, setLabel }
})
