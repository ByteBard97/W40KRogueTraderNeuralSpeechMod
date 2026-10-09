import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiRequestError, api } from '../api/client'
import type { OverrideBody, PoolSummary, QueueEntry } from '../api/types'

const NOT_FOUND = 404

export const usePoolsStore = defineStore('pools', () => {
  const summary = ref<PoolSummary | null>(null)
  const queue = ref<QueueEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const notBuilt = computed(() => summary.value === null && error.value === null && !loading.value && loaded.value)
  const loaded = ref(false)

  async function load() {
    loading.value = true
    error.value = null
    try {
      summary.value = await api.pools()
      queue.value = await api.poolQueue()
    } catch (e) {
      summary.value = null
      queue.value = []
      if (!(e instanceof ApiRequestError && e.status === NOT_FOUND)) error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
      loaded.value = true
    }
  }
  async function rebuild() {
    error.value = null
    try {
      await api.poolsRebuild()
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return
    }
    await load()
  }
  async function apply(body: OverrideBody) {
    try {
      await api.poolOverride(body)
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return
    }
    await load()
  }
  const accept = (entry: string) => apply({ entry })
  const move = (entry: string, target: Pick<OverrideBody, 'to' | 'slot' | 'speaker'>) => apply({ entry, ...target })

  return { summary, queue, loading, error, notBuilt, load, rebuild, accept, move }
})
