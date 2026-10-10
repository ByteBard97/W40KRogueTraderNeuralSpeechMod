import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import { createKeyedQueue } from './serial'
import type { MatchCounts, MatchFilter, MatchRowData, MatchValue, MatchesPage } from '../api/types'

const PAGE = 50
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** What the review queue shows first: flagged matches nobody has decided yet. */
export const DEFAULT_FILTER: MatchFilter = { group: 'flagged', state: 'unreviewed', speaker: '', q: '' }

type RowState = Pick<MatchRowData, 'decision' | 'effective'>

/** Does the row still belong in the server's list for the decision-state filter? */
function inState(row: MatchRowData, state: string | undefined): boolean {
  if (!state) return true
  if (state === 'unreviewed') return !row.decision
  if (state === 'reviewed') return !!row.decision
  return (row.effective || 'undecided') === state
}

const count = (n: number | undefined, by: number) => (n === undefined ? n : Math.max(0, n + by))

/** Move the progress numbers by one row going from `before` to `after`. Fields an older server omits stay absent. */
function bump(c: MatchCounts, row: MatchRowData, before: RowState, after: RowState): MatchCounts {
  const flag = (r: RowState, v: MatchValue) => (r.decision === v ? 1 : 0)
  const accepted = flag(after, 'accept') - flag(before, 'accept')
  const rejected = flag(after, 'reject') - flag(before, 'reject')
  const unrev = (r: RowState) => (r.decision ? 0 : 1)
  const out: MatchCounts = { ...c, undecided: count(c.undecided, (after.effective ? 0 : 1) - (before.effective ? 0 : 1)) as number }
  out.accepted = count(c.accepted, accepted)
  out.rejected = count(c.rejected, rejected)
  out.reviewed = count(c.reviewed, accepted + rejected)
  out.unreviewed = count(c.unreviewed, unrev(after) - unrev(before))
  out.flagged_unreviewed = count(c.flagged_unreviewed, row.flagged ? unrev(after) - unrev(before) : 0)
  return out
}

export const useMatchesStore = defineStore('matches', () => {
  const page = ref<MatchesPage | null>(null)
  const items = ref<MatchRowData[]>([])
  const filter = ref<MatchFilter>({ ...DEFAULT_FILTER })
  const counts = ref<MatchCounts | null>(null)
  const selectedId = ref<string | null>(null)
  const error = ref<string | null>(null)
  /** Pools wording for the Saved line: empty for a plain save. */
  const notice = ref('')
  const saved = ref(false)
  const poolsStale = ref(false)
  const pending = ref(0)
  const loading = computed(() => pending.value > 0)
  const saving = ref(0)
  /** Show more waits for the list to load and for saves to land, or its offset would be off. */
  const busy = computed(() => loading.value || saving.value > 0)
  let loadSeq = 0
  const enqueue = createKeyedQueue()
  const confirmed = new Map<string, RowState>()
  const versions = new Map<string, number>()

  const index = computed(() => items.value.findIndex((r) => r.id === selectedId.value))
  const current = computed(() => items.value[index.value] ?? null)

  /** A row that leaves (or rejoins) the filtered list moves the server's total with it. */
  function applyState(row: MatchRowData, next: RowState) {
    const was = inState(row, filter.value.state)
    const before = { decision: row.decision, effective: row.effective }
    Object.assign(row, next)
    const now = inState(row, filter.value.state)
    if (page.value && was !== now) page.value.total += now ? 1 : -1
    if (counts.value) counts.value = bump(counts.value, row, before, next)
  }

  /** The count comes from confirmed decisions only: an unsaved or failed one has not moved the server's list. */
  const serverCount = () => items.value.filter((r) => inState({ ...r, ...confirmed.get(r.id) }, filter.value.state)).length
  const matching = computed(() => items.value.filter((r) => inState(r, filter.value.state)).length)
  const remaining = computed(() => (page.value ? Math.max(0, page.value.total - matching.value) : 0))
  async function load(more = false) {
    if (more && busy.value) return
    const seq = ++loadSeq
    pending.value++
    error.value = null
    try {
      const p = await api.matches({ ...filter.value, offset: more ? serverCount() : 0, limit: PAGE })
      if (seq !== loadSeq) return
      page.value = p
      counts.value = p.counts
      poolsStale.value = !!p.pools_stale
      if (more) {
        const have = new Set(items.value.map((r) => r.id))
        items.value = [...items.value, ...p.items.filter((r) => !have.has(r.id))]
      } else {
        items.value = p.items
        confirmed.clear()
      }
      if (!items.value.some((r) => r.id === selectedId.value)) selectedId.value = items.value[0]?.id ?? null
    } catch (e) {
      if (seq === loadSeq) error.value = msg(e)
    } finally {
      pending.value--
    }
  }
  const setFilter = (f: MatchFilter) => { filter.value = { ...f }; selectedId.value = null; return load() }

  const select = (id: string | null) => { selectedId.value = id }

  /** Step the selection; at the end of what is loaded, fetch the next page first. */
  async function move(by: number) {
    if (!items.value.length) return
    let to = index.value + by
    if (to >= items.value.length && remaining.value > 0) await load(true)
    to = Math.min(Math.max(to, 0), items.value.length - 1)
    selectedId.value = items.value[to].id
  }

  /** Select the next row after the current one that has no decision. Returns false when there is none. */
  async function nextUnreviewed(): Promise<boolean> {
    const find = () => items.value.findIndex((r, i) => i > index.value && !r.decision)
    let i = find()
    if (i < 0 && remaining.value > 0) {
      await load(true)
      i = find()
    }
    if (i < 0) return false
    selectedId.value = items.value[i].id
    return true
  }

  /**
   * Optimistic: the row changes at once. Saves for one row go out in click order, and a failed save puts the
   * row back to the last confirmed decision, but only if nothing newer was clicked since. Pools rebuild is
   * deferred to the server (debounced), so a fast run of A/R presses does not rebuild per press.
   */
  async function decide(id: string, value: MatchValue) {
    const row = items.value.find((r) => r.id === id)
    if (!row) return
    if (!confirmed.has(id)) confirmed.set(id, { decision: row.decision, effective: row.effective })
    const version = (versions.get(id) ?? 0) + 1
    versions.set(id, version)
    const after = { decision: value, effective: value || (row.flagged ? '' : 'accept') } as RowState
    applyState(row, after)
    saving.value++
    try {
      const r = await enqueue(id, () => api.matchDecision(id, value, false))
      confirmed.set(id, after)
      poolsStale.value = !!r.pools_stale
      saved.value = true
      notice.value = r.pools_rebuilt ? `Pools rebuilt (${r.queue_entries} entries need review)` : r.pools_stale ? 'Pools update in a moment' : ''
    } catch (e) {
      error.value = msg(e)
      saved.value = false
      if (versions.get(id) !== version) return
      const back = confirmed.get(id)
      if (back && items.value.find((r) => r.id === id) === row) applyState(row, back)
    } finally {
      saving.value--
    }
  }

  /** Apply any deferred pools rebuild now (leaving the page, or before the owner looks at Pools). */
  async function flushPools() {
    if (!poolsStale.value) return
    try {
      const r = await api.matchesRebuild()
      poolsStale.value = false
      if (r.pools_rebuilt) notice.value = `Pools rebuilt (${r.queue_entries} entries need review)`
    } catch (e) {
      error.value = msg(e)
    }
  }

  return { page, items, filter, counts, selectedId, index, current, error, notice, saved, poolsStale, loading, busy, saving, remaining, load, setFilter, select, move, nextUnreviewed, decide, flushPools }
})
