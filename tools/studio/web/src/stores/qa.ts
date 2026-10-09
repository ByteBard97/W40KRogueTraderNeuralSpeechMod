import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import { createKeyedQueue } from './serial'
import type { QaClip, QaFacets, QaFilter, QaRun, QaStats, QaVerdict, QaVerdictValue } from '../api/types'

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
  const hasNext = ref(false)
  const stats = ref<QaStats>({ good: 0, bad: 0, unjudged: 0 })
  const error = ref<string | null>(null)
  const pending = ref(0)
  const loading = computed(() => pending.value > 0)
  /** With a verdict filter, judged rows leave the server's list while they stay on screen, so offsets drift.
   *  Then paging works by exclusion: always ask from the top and have the server skip the clips already shown. */
  const seen = ref<string[]>([])
  const trail = ref<string[][]>([])
  const byExclusion = () => !!filter.value.verdict
  const canPrev = computed(() => (byExclusion() ? trail.value.length > 0 : offset.value > 0))
  let pageSeq = 0
  let facetSeq = 0
  let runSeq = 0
  const enqueue = createKeyedQueue()
  const key = (guid: string, r = run.value) => `${r}|${guid}`
  const confirmed = new Map<string, QaVerdict | null>()
  const versions = new Map<string, number>()

  async function tracked(fn: () => Promise<void>) {
    pending.value++
    error.value = null
    try {
      await fn()
    } catch (e) {
      error.value = msg(e)
    } finally {
      pending.value--
    }
  }

  const loadRuns = () => tracked(async () => {
    const seq = ++runSeq
    const r = await api.qaRuns()
    if (seq !== runSeq) return
    runs.value = r
    if (!r.some((x) => x.id === run.value) && r.length) run.value = r[0].id
  })
  const loadFacets = () => tracked(async () => {
    const seq = ++facetSeq
    const f = await api.qaFacets(run.value)
    if (seq === facetSeq) facets.value = f
  })

  /** `skip` is what the exclusion paging has already shown; `applied` runs only when this response is the one used. */
  function fetchPage(at: number, skip: string[], applied?: () => void) {
    return tracked(async () => {
      const seq = ++pageSeq
      const exclude = byExclusion()
      const p = await api.qaClips(run.value, {
        ...filter.value, offset: exclude ? 0 : at, limit: QA_PAGE, ...(exclude && skip.length ? { exclude: skip.join(',') } : {}),
      })
      if (seq !== pageSeq) return
      applied?.()
      seen.value = exclude ? skip : []
      items.value = p.items
      offset.value = exclude ? skip.length : p.offset
      total.value = exclude ? p.total + skip.length : p.total   // the server counts only what is left after the skip
      hasNext.value = p.items.length > 0 && (exclude ? p.total - p.items.length > 0 : p.offset + p.items.length < p.total)
      stats.value = p.stats
    })
  }

  /** Page 0 also forgets the paging trail; other offsets only apply without a verdict filter. */
  const loadPage = (at = offset.value) => {
    if (at === 0) return fetchPage(0, [], () => { trail.value = [] })
    return fetchPage(at, seen.value)
  }
  const nextPage = () => {
    if (loading.value) return Promise.resolve()
    if (!byExclusion()) return fetchPage(offset.value + QA_PAGE, [])
    const before = seen.value
    return fetchPage(0, [...before, ...items.value.map((c) => c.guid)], () => { trail.value = [...trail.value, before] })
  }
  const prevPage = () => {
    if (loading.value) return Promise.resolve()
    if (!byExclusion()) return fetchPage(Math.max(0, offset.value - QA_PAGE), [])
    const back = trail.value[trail.value.length - 1] ?? []
    return fetchPage(0, back, () => { trail.value = trail.value.slice(0, -1) })
  }

  async function setRun(id: string) {
    run.value = id
    filter.value = { sort: filter.value.sort, seed: RANDOM_SEED }
    confirmed.clear()
    await Promise.all([loadFacets(), loadPage(0)])
  }
  const setFilter = (f: QaFilter) => { filter.value = { seed: RANDOM_SEED, ...f }; return loadPage(0) }

  const bump = (v: QaVerdictValue | undefined, by: 1 | -1) => {
    if (v) stats.value[v] += by
    else stats.value.unjudged += by
  }

  /**
   * Optimistic: the row and the counts change at once. Saves for one clip go out in click order, and a failed
   * save puts the row back to the last verdict the server confirmed, but only if nothing newer was clicked since.
   * `null` clears.
   */
  async function setVerdict(guid: string, verdict: QaVerdictValue | null, tags?: string[], note?: string) {
    const item = items.value.find((c) => c.guid === guid)
    if (!item) return
    const before = item.verdict
    const k = key(guid)
    if (!confirmed.has(k)) confirmed.set(k, before)
    const after = verdict === null ? null : { verdict, tags: tags ?? before?.tags ?? [], note: note ?? before?.note ?? '' }
    const version = (versions.get(k) ?? 0) + 1
    versions.set(k, version)
    item.verdict = after
    bump(before?.verdict, -1)
    bump(after?.verdict, 1)
    const body = { run: run.value, guid, verdict, tags: after?.tags ?? [], note: after?.note ?? '' }
    try {
      await enqueue(k, () => api.qaVerdict(body))
      confirmed.set(k, after)
    } catch (e) {
      error.value = msg(e)
      if (versions.get(k) !== version) return
      const back = confirmed.get(k) ?? null
      const row = items.value.find((c) => c.guid === guid)
      if (row !== item) return
      bump(item.verdict?.verdict, -1)
      item.verdict = back
      bump(back?.verdict, 1)
    }
  }

  /** The file stores tags and note with the verdict, so an unjudged clip becomes bad. */
  function setDetails(guid: string, tags: string[], note: string) {
    const v = items.value.find((c) => c.guid === guid)?.verdict
    return setVerdict(guid, v?.verdict ?? 'bad', tags, note)      // like the old page: tagging an unjudged clip marks it bad
  }

  return {
    runs, run, facets, filter, items, total, offset, stats, error, loading, hasNext, canPrev,
    loadRuns, loadFacets, loadPage, nextPage, prevPage, setRun, setFilter, setVerdict, setDetails,
  }
})
