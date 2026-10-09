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
  return { list, loading, error, byStatus, load }
})
