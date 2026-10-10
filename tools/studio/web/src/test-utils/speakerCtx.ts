import { computed, ref } from 'vue'
import { vi } from 'vitest'
import type { Candidate, DesignState, Line, SourceClip, Take } from '../api/types'
import { SPEAKER_CTX_KEY } from '../composables/useSpeakerContext'
import { DEFAULT_OPTIONS, type SpeakerContext } from '../composables/useSpeakerState'

export const cand = (id: string, over: Partial<Candidate> = {}): Candidate => ({
  id, file: `data/vd/${id}`, scores: { p_us: 0.1, top: 'england', p_top: 0.8 }, verdict: {}, gen: { seed: 7 }, ...over,
})

export const designState = (over: Partial<DesignState> = {}): DesignState => ({
  description: 'A calm woman.', text: 'Sample.', candidates: [cand('c0.wav'), cand('c1.wav'), cand('c2.wav')], order: ['c0.wav', 'c1.wav', 'c2.wav'], pick: null, clones: [], ...over,
})

export const lineOf = (guid: string, over: Partial<Line> = {}): Line => ({ guid, text: `Line ${guid}.`, emotion: 'neutral', intensity: 0.2, pace: 'normal', instruct: null, baseline: null, ...over })

export const takeOf = (id: string, over: Partial<Take> = {}): Take => ({
  id, raw: `data/t/${id}.wav`, text: 'Greetings.', guid: 'g1', reference: 'data/v/E1.wav', options: { ...DEFAULT_OPTIONS }, instruct: null, seed: 5,
  seconds: 2, audio_s: 3.1, rating: 0, note: '', fx: null, ...over,
} as Take)

/** A speaker context with every field a workbench component reads; `over` replaces any of them. */
export function makeCtx(over: Record<string, unknown> = {}): SpeakerContext {
  const selectedSources = ref(new Set<string>(['cand:c0.wav']))
  const src: SourceClip = { key: 'cand:c0.wav', label: 'candidate c0', wav: 'data/vd/c0.wav', text: 'Sample.', origin: 'designed' }
  const ctx = {
    slug: 'ruoldo',
    detail: ref({ summary: { slug: 'ruoldo', name: 'Governor Ruoldo', origin: 'designed', line_count: 2, status: 'source', has_pick: false }, clips: [], design: designState(), profile: null }),
    lines: ref([lineOf('g1'), lineOf('g2', { emotion: 'sad', text: 'Farewell.' })]),
    takes: ref<Take[]>([]),
    fxAvailable: ref<string[]>(['Clean', 'Servitor']),
    options: ref({ ...DEFAULT_OPTIONS }),
    seedPolicy: ref('new'),
    fxChosen: ref<string[]>([]),
    supplied: ref<SourceClip[]>([]),
    selectedSources,
    selectedLines: ref(new Set<string>(['g1', 'g2'])),
    chosenSources: computed(() => [src].filter((s) => selectedSources.value.has(s.key))),
    sources: computed(() => [src]),
    loading: ref(false), error: ref(null), notice: ref(''), noticeKind: ref('ok'),
    load: vi.fn(), refreshDetail: vi.fn(async () => undefined), addSupplied: vi.fn(), upsertTake: vi.fn(),
    saveProfile: vi.fn(), setActive: vi.fn(), registerPick: vi.fn(),
    ...over,
  }
  return ctx as unknown as SpeakerContext
}

export const withCtx = (ctx: SpeakerContext, extra: Record<string, unknown> = {}) => ({ global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx }, stubs: { RouterLink: { template: '<a><slot /></a>' } }, ...extra } })
