import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { api } from '../api/client'
import type { Line, ModelOptions, SourceClip, SpeakerDetail, Take } from '../api/types'

export const DEFAULT_OPTIONS: ModelOptions = {
  cfg: 2, timesteps: 10, seed: '', use_instruct: false, retry_badcase: false, normalize: false, continuation: false,
}

export interface SpeakerContext {
  slug: string
  detail: Ref<SpeakerDetail | null>
  lines: Ref<Line[]>
  takes: Ref<Take[]>
  fxAvailable: Ref<string[]>
  options: Ref<ModelOptions>
  fxChosen: Ref<string[]>
  supplied: Ref<SourceClip[]>
  selectedSources: Ref<Set<string>>
  selectedLines: Ref<Set<string>>
  sources: ComputedRef<SourceClip[]>
  chosenSources: ComputedRef<SourceClip[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  notice: Ref<string>
  load(): Promise<void>
  refreshDetail(): Promise<void>
  addSupplied(wav: string, text: string): void
  upsertTake(t: Take): void
  saveProfile(): Promise<void>
  setActive(): Promise<void>
  registerPick(): Promise<void>
}

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useSpeakerState(slug: string): SpeakerContext {
  const detail = ref<SpeakerDetail | null>(null)
  const lines = ref<Line[]>([])
  const takes = ref<Take[]>([])
  const fxAvailable = ref<string[]>([])
  const options = ref<ModelOptions>({ ...DEFAULT_OPTIONS })
  const fxChosen = ref<string[]>([])
  const supplied = ref<SourceClip[]>([])
  const selectedSources = ref<Set<string>>(new Set())
  const selectedLines = ref<Set<string>>(new Set())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const notice = ref('')

  const sources = computed<SourceClip[]>(() => {
    const d = detail.value
    if (!d) return supplied.value
    const real = d.clips.map((c) => ({ key: `real:${c.id}`, label: `${c.id}${c.curated_rank ? ` (curated #${c.curated_rank})` : ''}`, wav: c.wav, text: c.text, origin: 'real' as const }))
    const cands = (d.design?.candidates ?? []).map((c) => ({ key: `cand:${c.id}`, label: `candidate ${c.id.replace('.wav', '')}`, wav: c.file, text: d.design!.text, origin: 'designed' as const }))
    return [...real, ...cands, ...supplied.value]
  })

  const chosenSources = computed(() => sources.value.filter((s) => selectedSources.value.has(s.key)))

  function addSupplied(wav: string, text: string) {
    const key = `sup:${wav}`
    if (!supplied.value.some((s) => s.key === key)) supplied.value.push({ key, label: wav.split('/').pop() ?? wav, wav, text, origin: 'supplied' })
    selectedSources.value = new Set([...selectedSources.value, key])
  }

  function applyProfile(d: SpeakerDetail) {
    const p = d.profile
    if (!p) return
    options.value = { ...DEFAULT_OPTIONS, ...p.options }
    fxChosen.value = [...p.fx]
    selectedLines.value = new Set(p.test_lines)
    const hit = sources.value.find((s) => s.wav === p.source.wav)
    if (hit) selectedSources.value = new Set([hit.key])
    else if (p.source.wav) addSupplied(p.source.wav, p.source.text)
  }

  async function load() {
    loading.value = true
    error.value = null
    try {
      const [d, l, t, f] = await Promise.all([api.speaker(slug), api.lines(slug), api.takes(slug), api.fxPresets()])
      detail.value = d
      lines.value = l
      takes.value = t
      fxAvailable.value = f
      selectedSources.value = new Set()
      if (d.profile) applyProfile(d)
      if (!selectedSources.value.size) {
        const pick = d.design?.pick
        const first = pick ? sources.value.find((s) => s.key === `cand:${pick}`) : sources.value[0]
        if (first) selectedSources.value = new Set([first.key])
      }
    } catch (e) {
      error.value = msg(e)
    } finally {
      loading.value = false
    }
  }

  /** Re-read the speaker only. Unlike load() this keeps the ticked sources, lines and unsaved options. */
  async function refreshDetail() {
    detail.value = await api.speaker(slug)
  }

  function upsertTake(t: Take) {
    const i = takes.value.findIndex((x) => x.id === t.id)
    if (i >= 0) takes.value.splice(i, 1, t)
    else takes.value.unshift(t)
  }

  async function saveProfile() {
    const src = chosenSources.value[0]
    if (!src) {
      notice.value = 'Choose a source clip first.'
      return
    }
    try {
      await api.saveProfile(slug, {
        source: { wav: src.wav, text: src.text, origin: src.origin },
        options: options.value, fx: fxChosen.value, test_lines: [...selectedLines.value],
      } as never)
      notice.value = 'Profile saved.'
      const d = await api.speaker(slug)
      detail.value = d
    } catch (e) {
      notice.value = msg(e)
    }
  }

  async function setActive() {
    try {
      notice.value = `Active settings: ${(await api.setActive(slug)).active}`
    } catch (e) {
      notice.value = msg(e)
    }
  }

  async function registerPick() {
    try {
      const r = await api.register(slug)
      notice.value = `Registered ${r.registered.join(', ')} in the prompt bank.`
      await load()
    } catch (e) {
      notice.value = msg(e)
    }
  }

  return { slug, detail, lines, takes, fxAvailable, options, fxChosen, supplied, selectedSources, selectedLines, sources, chosenSources, loading, error, notice, load, refreshDetail, addSupplied, upsertTake, saveProfile, setActive, registerPick }
}
