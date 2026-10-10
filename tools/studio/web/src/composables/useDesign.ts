import { computed } from 'vue'
import { api } from '../api/client'
import type { Candidate, LiveTake, Verdict } from '../api/types'
import { useLiveTakesStore } from '../stores/liveTakes'
import { useSpeakerContext } from './useSpeakerContext'
import { useToasts } from './useToasts'

export const shortId = (id: string) => id.replace(/\.wav$/, '')
const idNumber = (id: string) => Number(/\d+/.exec(id)?.[0] ?? -1)
const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

/**
 * Ranking, verdicts, the explicit pick, description and Keep for the designed voice of this speaker page. Every change shows at once and is
 * sent to the server; if the server refuses, the page is re-read and the reason shown as a toast.
 */
export function useDesign() {
  const ctx = useSpeakerContext()
  const toasts = useToasts()
  const liveStore = useLiveTakesStore()

  const design = computed(() => ctx.detail.value?.design ?? null)
  const candidates = computed(() => design.value?.candidates ?? [])
  const pickId = computed(() => design.value?.pick ?? null)
  const scoredCount = computed(() => candidates.value.filter((c) => c.verdict.fit !== undefined).length)
  const nextId = computed(() => `c${Math.max(-1, ...candidates.value.map((c) => idNumber(c.id))) + 1}`)
  const liveTakes = computed(() => liveStore.forSlug(ctx.slug))

  async function run(change: () => void, send: () => Promise<unknown>) {
    change()
    try {
      await send()
    } catch (e) {
      toasts.error(message(e))
      await ctx.refreshDetail().catch(() => undefined)
    }
  }
  const find = (id: string): Candidate | undefined => candidates.value.find((c) => c.id === id)

  function setVerdict(id: string, patch: Verdict) {
    const c = find(id)
    if (!c) return Promise.resolve()
    return run(() => {
      const { accent_score: score, ...rest } = patch
      Object.assign(c.verdict, rest)
      if ('accent_score' in patch) {
        if (score === null || score === undefined) delete c.verdict.accent_score
        else c.verdict.accent_score = score
      }
    }, () => api.designVerdict(ctx.slug, { cand: id, ...patch }))
  }

  /** Pick or un-pick `id`. A pick is its own choice: it does not follow the ranking. */
  function togglePick(id: string) {
    const d = design.value
    if (!d) return Promise.resolve()
    const on = d.pick !== id
    return run(() => { d.pick = on ? id : null }, () => api.designVerdict(ctx.slug, { cand: id, pick: on }))
  }

  /** Reject or restore `id`. Rejecting the picked candidate also clears the pick, since a rejected pick cannot be registered. */
  function toggleReject(id: string) {
    const c = find(id)
    const d = design.value
    if (!c || !d) return Promise.resolve()
    const reject = !c.verdict.reject
    const clearPick = reject && d.pick === id
    return run(() => {
      c.verdict.reject = reject
      if (clearPick) d.pick = null
    }, () => api.designVerdict(ctx.slug, { cand: id, reject, ...(clearPick ? { pick: false } : {}) }))
  }

  function reorder(order: string[]) {
    const d = design.value
    if (!d) return Promise.resolve()
    return run(() => {
      d.order = order
      d.candidates.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id))
    }, () => api.designOrder(ctx.slug, order))
  }

  /** Saving writes the real overrides.json, so only a real change counts: not a focus-and-leave, not an empty box. */
  async function saveDescription(text: string) {
    const t = text.trim()
    if (!t || t === design.value?.description) return
    try {
      await api.designDescription(ctx.slug, t)
      await ctx.refreshDetail()
    } catch (e) {
      toasts.error(message(e))
    }
  }

  const keeping = new Set<string>()
  async function keep(take: LiveTake) {
    if (keeping.has(take.file)) return        // a double click must not keep the same take twice
    keeping.add(take.file)
    try {
      const { cand } = await api.designKeep(ctx.slug, take)
      liveStore.remove(ctx.slug, take)
      await ctx.refreshDetail()
      toasts.ok(`Kept as ${shortId(cand)}.`)
    } catch (e) {
      toasts.error(message(e))
    } finally {
      keeping.delete(take.file)
    }
  }

  return { design, candidates, pickId, scoredCount, nextId, liveTakes, setVerdict, togglePick, toggleReject, reorder, saveDescription, keep }
}
