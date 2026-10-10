import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { PoolRoute } from '../api/types'
import { usePoolsStore } from './pools'

export const ROUTES_PAGE = 50
const SEARCH_DEBOUNCE_MS = 300

export type DestFilter = '' | 'slot' | 'bank' | 'nobank' | 'narrator'
export const DEST_LABELS: Record<Exclude<DestFilter, ''>, string> = {
  slot: 'Shared slot voice',
  bank: 'Known speaker with a bank',
  nobank: 'Named NPC without a bank',
  narrator: 'Narrator',
}

/** The Routes table: every unnamed line and where it goes, with filters and 50-row pages. */
export const usePoolRoutesStore = defineStore('poolRoutes', () => {
  const pools = usePoolsStore()
  const q = ref('')
  const dest = ref<DestFilter>('')
  const slot = ref('')
  const lowConf = ref(false)
  const reviewOnly = ref(false)
  const offset = ref(0)
  const items = ref<PoolRoute[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let timer: ReturnType<typeof setTimeout> | undefined
  let ticket = 0

  const threshold = computed(() => pools.summary?.threshold ?? 0.8)
  const filters = computed(() => [
    ...(q.value.trim() ? [{ key: 'q', label: `“${q.value.trim()}”` }] : []),
    ...(dest.value ? [{ key: 'dest', label: DEST_LABELS[dest.value] }] : []),
    ...(slot.value ? [{ key: 'slot', label: pools.slots.find((s) => s.id === slot.value)?.name ?? slot.value }] : []),
    ...(lowConf.value ? [{ key: 'conf', label: `Below ${threshold.value}` }] : []),
    ...(reviewOnly.value ? [{ key: 'review', label: 'Needs review' }] : []),
  ])
  const last = computed(() => offset.value + ROUTES_PAGE >= total.value)
  const range = computed(() => ({ from: total.value ? offset.value + 1 : 0, to: Math.min(total.value, offset.value + items.value.length) }))

  async function load() {
    const mine = ++ticket
    loading.value = true
    error.value = null
    try {
      const d = dest.value
      const r = await api.poolRoutes({
        q: q.value.trim() || undefined,
        to: d === 'bank' || d === 'nobank' ? 'speaker' : d || undefined,
        bank: d === 'bank' ? 1 : d === 'nobank' ? 0 : undefined,
        slot: slot.value || undefined,
        conf_lt: lowConf.value ? threshold.value : undefined,
        queued: reviewOnly.value || undefined,
        offset: offset.value,
        limit: ROUTES_PAGE,
      })
      if (mine !== ticket) return
      items.value = r.items
      total.value = r.total
    } catch (e) {
      if (mine === ticket) error.value = e instanceof Error ? e.message : String(e)
    } finally {
      if (mine === ticket) loading.value = false
    }
  }

  function refilter() {
    clearTimeout(timer)
    offset.value = 0
    return load()
  }
  function search(text: string) {
    q.value = text
    clearTimeout(timer)
    timer = setTimeout(refilter, SEARCH_DEBOUNCE_MS)
  }
  function setDest(d: DestFilter) {
    dest.value = d
    if (d && d !== 'slot') slot.value = ''
    return refilter()
  }
  function setSlot(id: string) {
    slot.value = id
    if (id) dest.value = 'slot'
    return refilter()
  }
  function setLowConf(on: boolean) {
    lowConf.value = on
    return refilter()
  }
  function setReviewOnly(on: boolean) {
    reviewOnly.value = on
    return refilter()
  }
  function remove(key: string) {
    if (key === 'q') q.value = ''
    else if (key === 'dest') dest.value = ''
    else if (key === 'slot') slot.value = ''
    else if (key === 'conf') lowConf.value = false
    else if (key === 'review') reviewOnly.value = false
    return refilter()
  }
  function clear() {
    q.value = ''
    dest.value = ''
    slot.value = ''
    lowConf.value = false
    reviewOnly.value = false
    return refilter()
  }
  function step(delta: number) {
    offset.value = Math.max(0, offset.value + delta * ROUTES_PAGE)
    return load()
  }

  return { q, dest, slot, lowConf, reviewOnly, offset, items, total, loading, error, filters, last, range, load, search, setDest, setSlot, setLowConf, setReviewOnly, remove, clear, step }
})
