import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { Bg3Voice, CastAudition, CastCharacter, CastPage, LabelDef, LabelProgress, LabelValue } from '../api/types'

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export type CastFilter = 'all' | 'open' | 'cast'
export type CastKind = 'character' | 'slot' | 'all'

/** Casting: who still needs a voice, the BG3 voices on offer, and what has been chosen. The server is the source of truth. */
export const useCastingStore = defineStore('casting', () => {
  const page = ref<CastPage | null>(null)
  const voices = ref<Bg3Voice[]>([])
  const selected = ref<string | null>(null)
  const filter = ref<CastFilter>('open')
  /** Named characters, the nameless groups (pool slots), or both. */
  const kind = ref<CastKind>('character')
  const schema = ref<LabelDef[]>([])
  const progress = ref<LabelProgress | null>(null)
  const query = ref('')
  const error = ref<string | null>(null)
  const loading = ref(false)
  const auditions = ref<Record<string, CastAudition>>({})
  const auditioning = ref<string | null>(null)

  const characters = computed(() => page.value?.characters ?? [])
  const visible = computed(() => {
    const q = query.value.trim().toLowerCase()
    return characters.value.filter((c) =>
      (kind.value === 'all' || c.kind === kind.value) && (filter.value === 'all' || (filter.value === 'open') === !c.assignment) && (!q || `${c.speaker} ${c.role ?? ''}`.toLowerCase().includes(q)))
  })
  const current = computed<CastCharacter | null>(() => characters.value.find((c) => c.speaker === selected.value) ?? visible.value[0] ?? null)
  const counts = computed(() => ({ total: page.value?.total ?? 0, assigned: characters.value.filter((c) => c.assignment).length }))
  /** Lines still waiting for a cast voice, so the progress reads in what the player will hear. */
  const linesLeft = computed(() => characters.value.filter((c) => !c.assignment).reduce((n, c) => n + c.lines, 0))

  async function load() {
    loading.value = true
    error.value = null
    try {
      const [p, v, l] = await Promise.all([api.casting(), api.castingVoices(), api.castLabels()])
      page.value = p
      voices.value = v
      schema.value = l.schema
      progress.value = l.progress
    } catch (e) {
      error.value = msg(e)
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    const [p, v] = await Promise.all([api.casting(), api.castingVoices()])
    page.value = p
    voices.value = v
  }

  async function assign(speaker: string, bg3: string | null) {
    error.value = null
    try {
      await api.castAssign(speaker, bg3)
      await refresh()
    } catch (e) {
      error.value = msg(e)
    }
  }

  async function setPortrait(speaker: string, portrait: string | null) {
    try {
      await api.castPortrait(speaker, portrait)
      await refresh()
    } catch (e) {
      error.value = msg(e)
    }
  }

  async function audition(speaker: string, bg3: string, line = 0) {
    const key = `${speaker}|${bg3}`
    auditioning.value = key
    error.value = null
    try {
      auditions.value = { ...auditions.value, [key]: await api.castAudition(speaker, bg3, 0, line) }
    } catch (e) {
      error.value = msg(e)
    } finally {
      auditioning.value = null
    }
  }

  /** Set one label on a voice (an empty value clears it). The list updates at once; a failed save puts it back. */
  async function setLabel(slug: string, key: string, value: LabelValue | null) {
    const v = voices.value.find((x) => x.slug === slug)
    if (!v) return
    const before = { mine: { ...v.mine }, labels: { ...v.labels }, complete: v.complete }
    const empty = value === null || value === '' || (Array.isArray(value) && !value.length)
    v.mine = { ...v.mine, [key]: empty ? undefined : value }
    if (!empty) v.labels = { ...v.labels, [key]: value }
    v.complete = schema.value.filter((d) => d.required).every((d) => v.mine[d.key] !== undefined && v.mine[d.key] !== '')
    try {
      const mine = await api.castLabelSet(slug, key, empty ? null : value)
      v.mine = mine
      if (empty) {
        voices.value = await api.castingVoices()          // a cleared label falls back to the automatic guess, which only the server knows
      }
      progress.value = (await api.castLabels()).progress
    } catch (e) {
      v.mine = before.mine
      v.labels = before.labels
      v.complete = before.complete
      error.value = msg(e)
    }
  }

  const select = (speaker: string) => { selected.value = speaker }

  /** Next character without a voice, after the current one (wraps), so assigning can flow down the list. */
  function nextOpen() {
    const list = characters.value
    const at = list.findIndex((c) => c.speaker === current.value?.speaker)
    const next = [...list.slice(at + 1), ...list.slice(0, at + 1)].find((c) => !c.assignment)
    if (next) selected.value = next.speaker
  }

  return { page, voices, selected, filter, kind, schema, progress, query, error, loading, auditions, auditioning, characters, visible, current, counts, linesLeft,
    load, assign, setPortrait, audition, select, nextOpen, setLabel }
})
