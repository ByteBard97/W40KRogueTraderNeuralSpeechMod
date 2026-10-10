import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { ApiRequestError, api } from '../api/client'
import type { NewSlotBody, OverrideBody, PoolSlot, PoolSummary, QueueEntry } from '../api/types'
import { useToasts } from '../composables/useToasts'
import { type MoveTarget, NEW_VOICE_VALUE, parseTarget, routeValue, slotValue, targetLabel } from '../utils/poolTargets'
import { useNavCountsStore } from './navCounts'

const NOT_FOUND = 404
const errText = (e: unknown) => (e instanceof Error ? e.message : String(e))
const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`

export type SlotCheck = 'unchecked' | 'clean' | 'wrong'

/** A slot counts as spot-checked once some lines were marked and none were wrong. A wrong mark asks for a re-check. */
export function slotCheck(s: Pick<PoolSlot, 'spot'>): SlotCheck {
  if (s.spot.wrong > 0) return 'wrong'
  return s.spot.checked > 0 ? 'clean' : 'unchecked'
}

export const usePoolsStore = defineStore('pools', () => {
  const toasts = useToasts()
  const summary = ref<PoolSummary | null>(null)
  const queue = ref<QueueEntry[]>([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref<string | null>(null)
  /** Bumped after every load so tables that page on their own know to refetch. */
  const revision = ref(0)
  /** Queue keys skipped this session, in the order they were skipped. They go to the end of the queue; nothing is saved. */
  const skipped = ref<string[]>([])
  const cursor = ref(0)
  /** Entries accepted or moved this session, for the progress bar. */
  const handled = ref(0)
  /** Lines in the review queue before this session started handling it. */
  const startEntries = ref(0)

  /** The "Move to" choice per queue entry; absent means "the current guess". */
  const choices = reactive<Record<string, string>>({})
  /** Queue key whose "New designed voice" form is open. */
  const creating = ref<string | null>(null)

  const notBuilt = computed(() => summary.value === null && error.value === null && !loading.value && loaded.value)
  const slots = computed(() => summary.value?.slots ?? [])
  const ordered = computed(() => {
    const skip = skipped.value
    return [...queue.value.filter((e) => !skip.includes(e.key)), ...skip.flatMap((k) => queue.value.filter((e) => e.key === k))]
  })
  const current = computed(() => ordered.value[cursor.value] ?? null)
  const checkedSlots = computed(() => slots.value.filter((s) => slotCheck(s) === 'clean').length)
  const nextUnchecked = computed(() => slots.value.find((s) => slotCheck(s) !== 'clean') ?? null)
  const reviewFraction = computed(() => {
    const total = Math.max(startEntries.value, handled.value + queue.value.length)
    return total ? Math.min(1, handled.value / total) : 0
  })

  function clampCursor() {
    cursor.value = Math.min(Math.max(0, cursor.value), Math.max(0, ordered.value.length - 1))
  }
  const moveCursor = (delta: number) => {
    cursor.value += delta
    clampCursor()
  }
  const select = (key: string) => {
    const i = ordered.value.findIndex((e) => e.key === key)
    if (i >= 0) cursor.value = i
  }

  async function load() {
    loading.value = true
    error.value = null
    try {
      summary.value = await api.pools()
      queue.value = await api.poolQueue()
      if (!startEntries.value) startEntries.value = queue.value.length
      skipped.value = skipped.value.filter((k) => queue.value.some((e) => e.key === k))
      clampCursor()
    } catch (e) {
      summary.value = null
      queue.value = []
      if (!(e instanceof ApiRequestError && e.status === NOT_FOUND)) error.value = errText(e)
    } finally {
      loading.value = false
      loaded.value = true
      revision.value += 1
      if (summary.value) useNavCountsStore().pools = summary.value.queue_entries
    }
  }

  async function rebuild() {
    error.value = null
    try {
      await api.poolsRebuild()
    } catch (e) {
      toasts.error(`Rebuild failed: ${errText(e)}`, rebuild)
      return
    }
    skipped.value = []
    startEntries.value = 0
    handled.value = 0
    await load()
    toasts.ok('Routing rebuilt. Your decisions were kept.')
  }

  /** Put routes back exactly as they were (Undo on Accept, Move and a per-line change). */
  async function restore(previous: Record<string, unknown>, handledBack = 0) {
    try {
      await api.poolRestore(previous)
      handled.value = Math.max(0, handled.value - handledBack)
      await load()
    } catch (e) {
      toasts.error(`Undo failed: ${errText(e)}`)
    }
  }

  /** Apply an override and offer Undo when the server sent the previous routes. Returns whether it worked. */
  async function apply(body: OverrideBody, message: (changed: number) => string, handledNow = 0): Promise<boolean> {
    try {
      const r = await api.poolOverride(body)
      handled.value += handledNow
      const previous = r.undo?.previous
      if (previous && Object.keys(previous).length) toasts.undo(message(r.changed), () => void restore(previous, handledNow))
      else toasts.ok(message(r.changed))
    } catch (e) {
      toasts.error(errText(e))
      return false
    }
    await load()
    return true
  }

  const entryName = (e: QueueEntry) => e.name ?? e.label

  function accept(e: QueueEntry) {
    if (!e.entry) return Promise.resolve(false)
    const dest = targetLabel(e.slot ? slotValue(e.slot) : e.speaker ? `speaker:${e.speaker}` : 'narrator', slots.value)
    return apply({ entry: e.entry }, (n) => `Accepted ${entryName(e)} → ${dest} · ${plural(n, 'line', 'lines')}`, 1)
  }

  function move(e: QueueEntry, target: MoveTarget, valueForLabel: string) {
    if (!e.entry) return Promise.resolve(false)
    const dest = targetLabel(valueForLabel, slots.value)
    return apply({ entry: e.entry, ...target }, (n) => `Moved ${entryName(e)} → ${dest} · ${plural(n, 'line', 'lines')}`, 1)
  }

  /** Per-line change from the routes table. */
  function moveLine(guid: string, target: MoveTarget, valueForLabel: string) {
    return apply({ guids: [guid], ...target }, () => `Line moved → ${targetLabel(valueForLabel, slots.value)}`)
  }

  const chosen = (e: QueueEntry) => choices[e.key] ?? routeValue(e)
  const guessIsChosen = (e: QueueEntry) => chosen(e) === routeValue(e)
  function setChoice(e: QueueEntry, value: string) {
    choices[e.key] = value
    creating.value = value === NEW_VOICE_VALUE ? e.key : null
  }
  /** Send the entry to the chosen target; the "new voice" choice opens its form instead. */
  async function moveChosen(e: QueueEntry) {
    const v = chosen(e)
    if (v === NEW_VOICE_VALUE) {
      creating.value = e.key
      return false
    }
    const target = parseTarget(v)
    if (!target) return false
    delete choices[e.key]
    return move(e, target, v)
  }
  function cancelCreate(e: QueueEntry) {
    delete choices[e.key]
    creating.value = null
  }

  function skip(e: QueueEntry) {
    if (ordered.value.length < 2 || skipped.value.includes(e.key)) return
    skipped.value = [...skipped.value, e.key]
    clampCursor()
  }

  async function createSlot(body: NewSlotBody): Promise<PoolSlot | null> {
    try {
      const slot = await api.poolCreateSlot(body)
      toasts.ok(`Created voice ${slot.name}. Design it under Speakers.`)
      await load()
      return slot
    } catch (e) {
      toasts.error(errText(e))
      return null
    }
  }

  async function moveToNewVoice(e: QueueEntry, body: NewSlotBody) {
    const slot = await createSlot(body)
    if (slot) {
      creating.value = null
      delete choices[e.key]
      await move(e, { to: 'slot', slot: slot.id }, slotValue(slot.id))
    }
    return slot
  }

  async function rename(id: string, name: string) {
    try {
      await api.poolRename(id, name)
      await load()
    } catch (e) {
      toasts.error(`Rename failed: ${errText(e)}`)
    }
  }

  async function merge(id: string, into: string) {
    const from = slots.value.find((s) => s.id === id)?.name ?? id
    const to = slots.value.find((s) => s.id === into)?.name ?? into
    try {
      const r = await api.poolMerge(id, into)
      toasts.undo(`Merged ${from} into ${to} · ${plural(r.changed, 'line', 'lines')} moved`, () => void unmerge(id, from))
    } catch (e) {
      toasts.error(`Merge failed: ${errText(e)}`)
      return
    }
    await load()
  }

  async function unmerge(id: string, name: string) {
    try {
      await api.poolUnmerge(id)
      toasts.ok(`${name} is back`)
      await load()
    } catch (e) {
      toasts.error(`Undo failed: ${errText(e)}`)
    }
  }

  async function recordSpot(slotId: string, results: Record<string, boolean>) {
    try {
      const r = await api.poolSpotRecord(slotId, results)
      toasts.ok(r.wrong ? `Spot check saved · ${r.wrong} wrong. Check another 20 to be sure.` : `Spot check saved · ${plural(r.checked, 'line', 'lines')} checked, none wrong`)
      await load()
      return r
    } catch (e) {
      toasts.error(`Spot check failed: ${errText(e)}`)
      return null
    }
  }

  return {
    summary, queue, loading, error, notBuilt, revision, skipped, cursor, handled,
    choices, creating, chosen, guessIsChosen, setChoice, moveChosen, cancelCreate,
    slots, ordered, current, checkedSlots, nextUnchecked, reviewFraction,
    load, rebuild, accept, move, moveLine, skip, moveCursor, select, createSlot, moveToNewVoice, rename, merge, unmerge, recordSpot,
  }
})
