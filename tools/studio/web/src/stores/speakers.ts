import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { SpeakerStatus, SpeakerSummary } from '../api/types'

export const useSpeakersStore = defineStore('speakers', () => {
  const list = ref<SpeakerSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const byStatus = computed(() => {
    const g: Record<SpeakerStatus, SpeakerSummary[]> = { needs_voice: [], source: [], profile: [] }
    for (const s of list.value) g[s.status].push(s)
    return g
  })

  const pickedCount = computed(() => list.value.filter((s) => s.has_pick).length)

  /** 1-based place of a speaker in the list (the order the list page uses), or index 0 when unknown. */
  function position(slug: string) {
    return { index: list.value.findIndex((s) => s.slug === slug) + 1, total: list.value.length }
  }

  function neighbours(slug: string): { prev: string | null; next: string | null } {
    const i = list.value.findIndex((s) => s.slug === slug)
    const n = list.value.length
    if (i < 0 || n < 2) return { prev: null, next: null }
    return { prev: list.value[(i - 1 + n) % n].slug, next: list.value[(i + 1) % n].slug }
  }

  function setPick(slug: string, hasPick: boolean) {
    const s = list.value.find((x) => x.slug === slug)
    if (s) s.has_pick = hasPick
  }

  async function registerAll() {
    const r = await api.registerAll()
    await load()
    return r
  }

  async function load() {
    loading.value = true
    error.value = null
    try {
      list.value = await api.speakers()
    } catch (e) {
      list.value = []
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }
  return { list, loading, error, byStatus, pickedCount, position, neighbours, setPick, registerAll, load }
})
