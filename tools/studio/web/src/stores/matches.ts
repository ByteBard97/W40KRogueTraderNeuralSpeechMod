import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import { createKeyedQueue } from './serial'
import type { MatchFilter, MatchRowData, MatchValue, MatchesPage } from '../api/types'

const PAGE = 50
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

type RowState = Pick<MatchRowData, 'decision' | 'effective'>

/** Does the row still belong in the server's list for the decision-state filter? */
function inState(row: MatchRowData, state: string | undefined): boolean {
  if (!state) return true
  return (row.effective || 'undecided') === state
}

export const useMatchesStore = defineStore('matches', () => {
  const page = ref<MatchesPage | null>(null)
  const items = ref<MatchRowData[]>([])
  const filter = ref<MatchFilter>({})
  const error = ref<string | null>(null)
  const notice = ref('')
  const pending = ref(0)
  const loading = computed(() => pending.value > 0)
  let loadSeq = 0
  const enqueue = createKeyedQueue()
  const confirmed = new Map<string, RowState>()
  const versions = new Map<string, number>()

  /** A row that leaves (or rejoins) the filtered list moves the server's total with it. */
  function applyState(row: MatchRowData, next: RowState) {
    const was = inState(row, filter.value.state)
    Object.assign(row, next)
    const now = inState(row, filter.value.state)
    if (page.value && was !== now) page.value.total += now ? 1 : -1
  }

  /** Rows decided since they loaded may no longer match the state filter, so they no longer count towards the server's offset. */
  const matching = computed(() => items.value.filter((r) => inState(r, filter.value.state)).length)
  const remaining = computed(() => (page.value ? Math.max(0, page.value.total - matching.value) : 0))

  async function load(more = false) {
    const seq = ++loadSeq
    pending.value++
    error.value = null
    try {
      const p = await api.matches({ ...filter.value, offset: more ? matching.value : 0, limit: PAGE })
      if (seq !== loadSeq) return
      page.value = p
      items.value = more ? [...items.value, ...p.items] : p.items
      if (!more) { confirmed.clear() }
    } catch (e) {
      if (seq === loadSeq) error.value = msg(e)
    } finally {
      pending.value--
    }
  }
  const setFilter = (f: MatchFilter) => { filter.value = f; return load() }

  /**
   * Optimistic: the select changes at once. Saves for one row go out in click order, and a failed save puts the
   * row back to the last confirmed decision, but only if nothing newer was clicked since.
   */
  async function decide(id: string, value: MatchValue) {
    const row = items.value.find((r) => r.id === id)
    if (!row) return
    if (!confirmed.has(id)) confirmed.set(id, { decision: row.decision, effective: row.effective })
    const version = (versions.get(id) ?? 0) + 1
    versions.set(id, version)
    const after = { decision: value, effective: value || (row.flagged ? '' : 'accept') } as RowState
    applyState(row, after)
    try {
      const r = await enqueue(id, () => api.matchDecision(id, value))
      confirmed.set(id, after)
      notice.value = r.pools_rebuilt ? `Saved. Pools rebuilt (${r.queue_entries} entries need review).` : 'Saved.'
    } catch (e) {
      error.value = msg(e)
      if (versions.get(id) !== version) return
      const back = confirmed.get(id)
      if (back && items.value.find((r) => r.id === id) === row) applyState(row, back)
    }
  }
  return { page, items, filter, error, notice, loading, remaining, load, setFilter, decide }
})
