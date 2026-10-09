import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { QaClip, QaFacets, QaFilter, QaRun, QaStats, QaVerdictValue } from '../api/types'

export const QA_PAGE = 40
const DEFAULT_RUN = 'export'
const RANDOM_SEED = 1
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export const useQaStore = defineStore('qa', () => {
  const runs = ref<QaRun[]>([])
  const run = ref(DEFAULT_RUN)
  const facets = ref<QaFacets>({ speakers: [], refs: [], engines: [], flags: [] })
  const filter = ref<QaFilter>({ sort: 'suspicious', seed: RANDOM_SEED })
  const items = ref<QaClip[]>([])
  const total = ref(0)
  const offset = ref(0)
  const stats = ref<QaStats>({ good: 0, bad: 0, unjudged: 0 })
  const error = ref<string | null>(null)
  const loading = ref(false)

  async function guarded(fn: () => Promise<void>) {
    loading.value = true
    error.value = null
    try {
      await fn()
    } catch (e) {
      error.value = msg(e)
    } finally {
      loading.value = false
    }
  }

  const loadRuns = () => guarded(async () => {
    runs.value = await api.qaRuns()
    if (!runs.value.some((r) => r.id === run.value) && runs.value.length) run.value = runs.value[0].id
  })
  const loadFacets = () => guarded(async () => { facets.value = await api.qaFacets(run.value) })
  const loadPage = (at = offset.value) => guarded(async () => {
    const p = await api.qaClips(run.value, { ...filter.value, offset: at, limit: QA_PAGE })
    items.value = p.items
    total.value = p.total
    offset.value = p.offset
    stats.value = p.stats
  })

  async function setRun(id: string) {
    run.value = id
    filter.value = { sort: filter.value.sort, seed: RANDOM_SEED }
    await Promise.all([loadFacets(), loadPage(0)])
  }
  const setFilter = (f: QaFilter) => { filter.value = { seed: RANDOM_SEED, ...f }; return loadPage(0) }

  const bump = (v: QaVerdictValue | undefined, by: 1 | -1) => {
    if (v) stats.value[v] += by
    else stats.value.unjudged += by
  }

  /** Optimistic: the row and the counts change at once and go back if the save fails. `null` clears. */
  async function setVerdict(guid: string, verdict: QaVerdictValue | null, tags?: string[], note?: string) {
    const item = items.value.find((c) => c.guid === guid)
    if (!item) return
    const before = item.verdict
    const after = verdict === null ? null : { verdict, tags: tags ?? before?.tags ?? [], note: note ?? before?.note ?? '' }
    item.verdict = after
    bump(before?.verdict, -1)
    bump(after?.verdict, 1)
    try {
      await api.qaVerdict({ run: run.value, guid, verdict, tags: after?.tags ?? [], note: after?.note ?? '' })
    } catch (e) {
      item.verdict = before
      bump(after?.verdict, -1)
      bump(before?.verdict, 1)
      error.value = msg(e)
    }
  }

  /** Tags and note only make sense on a judged clip (the file stores them with the verdict). */
  function setDetails(guid: string, tags: string[], note: string) {
    const v = items.value.find((c) => c.guid === guid)?.verdict
    return v ? setVerdict(guid, v.verdict, tags, note) : Promise.resolve()
  }

  return { runs, run, facets, filter, items, total, offset, stats, error, loading, loadRuns, loadFacets, loadPage, setRun, setFilter, setVerdict, setDetails }
})
