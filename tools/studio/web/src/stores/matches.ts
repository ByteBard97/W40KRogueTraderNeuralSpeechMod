import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { MatchFilter, MatchRowData, MatchValue, MatchesPage } from '../api/types'

const PAGE = 50
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export const useMatchesStore = defineStore('matches', () => {
  const page = ref<MatchesPage | null>(null)
  const items = ref<MatchRowData[]>([])
  const filter = ref<MatchFilter>({})
  const error = ref<string | null>(null)
  const notice = ref('')
  const loading = ref(false)

  async function load(more = false) {
    loading.value = true
    error.value = null
    try {
      const p = await api.matches({ ...filter.value, offset: more ? items.value.length : 0, limit: PAGE })
      page.value = p
      items.value = more ? [...items.value, ...p.items] : p.items
    } catch (e) {
      error.value = msg(e)
    } finally {
      loading.value = false
    }
  }
  const setFilter = (f: MatchFilter) => { filter.value = f; return load() }

  /** Optimistic: the select changes at once and goes back if the server refuses. */
  async function decide(id: string, value: MatchValue) {
    const row = items.value.find((r) => r.id === id)
    if (!row) return
    const before = { decision: row.decision, effective: row.effective }
    row.decision = value
    row.effective = value || (row.flagged ? '' : 'accept')
    try {
      const r = await api.matchDecision(id, value)
      notice.value = r.pools_rebuilt ? `Saved. Pools rebuilt (${r.queue_entries} entries need review).` : 'Saved.'
    } catch (e) {
      Object.assign(row, before)
      error.value = msg(e)
    }
  }
  return { page, items, filter, error, notice, loading, load, setFilter, decide }
})
