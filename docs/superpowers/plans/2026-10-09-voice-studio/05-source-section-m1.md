# Voice Studio first slice, part 5 of 7: Source section (milestone M1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Task 12. Vue app: real clips, supplied wav, candidate ranker, live design. Ends at milestone M1 (audition usable).
**Previous part:** [Web shell, speakers list, speaker state](04-web-shell-and-speakers.md). **Next part:** [Lines, options, FX and results](06-lines-options-fx-results.md).

## Global Constraints

- Local only: the server binds `127.0.0.1`; audio is extracted from the user's game files and is never published.
- File serving: resolve the path, require it to sit under one of `data/voices`, `data/render`, `data/studio`, `data/voice_design`, and to be a file; otherwise 404.
- Nothing in the app or the tests deletes files. Tests write only under pytest `tmp_path`; manual checks must not touch real audit/manifest data (back up and compare before/after).
- Do not run the real model or any GPU job in this plan's automated steps; use the mock backend. The real-model check is a manual step for when the user says the GPU is free.
- Do not `git commit` or `git push` unless the repo owner says so. Steps named "Checkpoint" run `git status` and stop. If the owner asks for commits: plain human messages, no AI/Claude attribution of any kind.
- Reuse existing JSON schemas as-is: `audit.json`, `design_manifest.json`, `overrides.json`, `scores.json`, `prompts.json`, `catalog.json`, `jobs.jsonl`, `export/index.json`, FX `scenarios.json` and `presets.json`.
- No magic numbers in frontend code; files under 500 lines; `<script setup lang="ts">`, order script / template / `<style scoped>`.
- Model backend states shown to the user: `down`, `ready`, `busy`. (Spec deviation: "loading" is shown as `down` because the backend only starts listening after the model is loaded.)
- API framework: stdlib `http.server` (spec open question resolved: FastAPI is not installed cleanly here and the existing tools are stdlib).

---

### Task 12: Source section (real clips, supplied wav, candidate ranker, live design)

**Files:**
- Create: `src/components/source/{SourcePanel,RealClipList,SuppliedClip,CandidateRanker,DesignPanel}.vue`
- Modify: `src/views/SpeakerView.vue` (render `SourcePanel`)
- Tests: `src/components/source/CandidateRanker.test.ts`, `RealClipList.test.ts`, `DesignPanel.test.ts`

**Interfaces:**
- Consumes: speaker context, `api`, `useModelStore`, `moveItem`, `ClipCompare`/`useAudioPlayer`, `StarRating`.
- Produces:
  - `<CandidateRanker :candidates="Candidate[]" @reorder="string[]" @verdict="{cand, ...}" />` renders rows in the given order with rank numbers, drag handles (native HTML5 drag), up/down buttons (keyboard-accessible), accent buttons, fit stars, reject toggle, p_us chip, play button. Emits `reorder` with the new full id order (computed with `moveItem`) and `verdict` with `{cand, accent?|fit?|reject?}`.
  - `<RealClipList :clips="RealClip[]" />` ticks sources through context `selectedSources` (keys `real:<id>`), shows duration, curated badge, noise chip, transcript, play button; empty state "No real clips for this speaker."
  - `<SuppliedClip />`: path + transcript inputs, button "Add as source" calling `ctx.addSupplied`.
  - `<DesignPanel />`: description textarea (saved via `api.designDescription` on blur), live-design controls (seed, cfg, steps, Generate) disabled with `model.reason` unless `model.ready`, a list of this session's live takes (play, seed chip that refills the seed field, Keep), and the `CandidateRanker`. After Keep/verdict/reorder it reloads via `ctx.load()`.
  - `<SourcePanel />`: `SectionCard "Source"`; shows `RealClipList` when `detail.clips.length` or origin is `real`; shows `DesignPanel` when `detail.design`; always shows `SuppliedClip`.

- [ ] **Step 1: Write the failing tests**

`src/components/source/CandidateRanker.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import CandidateRanker from './CandidateRanker.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const cands = ['c0.wav', 'c1.wav', 'c2.wav'].map((id, i) => ({
  id, file: `data/vd/${id}`, scores: { p_us: 0.1 * (i + 1), top: 'england', p_top: 0.8 }, verdict: {}, gen: null,
}))

describe('CandidateRanker', () => {
  it('shows rank numbers in the given order', () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: ['c1.wav'] } })
    const rows = w.findAll('.cand')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('c1')            // ranked ones first
  })

  it('moves a candidate down with the button and emits the full new order', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    await w.findAll('.cand')[0].find('[data-move="down"]').trigger('click')
    expect(w.emitted('reorder')![0]).toEqual([['c1.wav', 'c0.wav', 'c2.wav']])
  })

  it('moves up with the button and does nothing at the edges', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    await w.findAll('.cand')[2].find('[data-move="up"]').trigger('click')
    expect(w.emitted('reorder')![0]).toEqual([['c0.wav', 'c2.wav', 'c1.wav']])
    await w.findAll('.cand')[0].find('[data-move="up"]').trigger('click')
    expect(w.emitted('reorder')).toHaveLength(1)
  })

  it('reorders by drag and drop', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    const rows = w.findAll('.cand')
    await rows[0].trigger('dragstart')
    await rows[2].trigger('drop')
    expect(w.emitted('reorder')![0]).toEqual([['c1.wav', 'c2.wav', 'c0.wav']])
  })

  it('emits verdicts for accent, fit and reject', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    const row = w.findAll('.cand')[0]
    await row.find('[data-accent="british"]').trigger('click')
    await row.find('[data-reject]').trigger('click')
    expect(w.emitted('verdict')![0]).toEqual([{ cand: 'c0.wav', accent: 'british' }])
    expect(w.emitted('verdict')![1]).toEqual([{ cand: 'c0.wav', reject: true }])
  })

  it('shows an empty state with no candidates', () => {
    const w = mount(CandidateRanker, { props: { candidates: [], order: [] } })
    expect(w.text()).toContain('No candidates')
  })

  it('ticks a candidate as a clone source through the speaker context, and hides the box without one', async () => {
    const ctx = { selectedSources: ref(new Set<string>()) }
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.findAll('input[data-source]')[1].setValue(true)
    expect([...ctx.selectedSources.value]).toEqual(['cand:c1.wav'])
    await w.findAll('input[data-source]')[1].setValue(false)
    expect(ctx.selectedSources.value.size).toBe(0)
    const bare = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    expect(bare.find('input[data-source]').exists()).toBe(false)
  })

  it('marks candidates that have no recorded seed', () => {
    const withSeed = { ...cands[0], id: 'c9.wav', gen: { seed: 7 } }
    const w = mount(CandidateRanker, { props: { candidates: [cands[0], withSeed], order: [] } })
    const rows = w.findAll('.cand')
    expect(rows[0].find('[data-no-seed]').exists()).toBe(true)
    expect(rows[1].find('[data-no-seed]').exists()).toBe(false)
    expect(rows[1].text()).toContain('seed 7')
  })
})
```

`src/components/source/RealClipList.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import RealClipList from './RealClipList.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const clips = [
  { id: 'E1', wav: 'data/v/E1.wav', duration: 5, text: 'Hello.', curated_rank: 1, noise_db: -60 },
  { id: 'E2', wav: 'data/v/E2.wav', duration: 3, text: 'Bye.', curated_rank: null, noise_db: null },
]

function mountWith(selected: string[]) {
  const ctx = { selectedSources: ref(new Set(selected)) }
  return { ctx, w: mount(RealClipList, { props: { clips }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('RealClipList', () => {
  it('ticks and unticks sources through the context', async () => {
    const { ctx, w } = mountWith(['real:E1'])
    const boxes = w.findAll('input[type=checkbox]')
    expect((boxes[0].element as HTMLInputElement).checked).toBe(true)
    await boxes[1].setValue(true)
    expect([...ctx.selectedSources.value].sort()).toEqual(['real:E1', 'real:E2'])
    await boxes[0].setValue(false)
    expect([...ctx.selectedSources.value]).toEqual(['real:E2'])
  })

  it('shows the curated badge and an empty message', () => {
    const { w } = mountWith([])
    expect(w.text()).toContain('curated #1')
    const empty = mount(RealClipList, { props: { clips: [] }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: { selectedSources: ref(new Set()) } } } })
    expect(empty.text()).toContain('No real clips')
  })
})
```

`src/components/source/DesignPanel.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { useModelStore } from '../../stores/model'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))
vi.mock('../../api/client', () => ({
  api: { designGenerate: vi.fn(), designKeep: vi.fn(), designVerdict: vi.fn(), designOrder: vi.fn(), designDescription: vi.fn() },
}))

import DesignPanel from './DesignPanel.vue'

const design = { description: 'A calm woman.', text: 'Sample.', order: [], pick: null, candidates: [] }
function mountPanel() {
  const ctx = { slug: 'muaran', detail: ref({ design }), load: vi.fn() }
  return { ctx, w: mount(DesignPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('DesignPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('disables Generate with a reason while the model is down', () => {
    const { w } = mountPanel()
    const btn = w.find('[data-generate]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/not running/i)
  })

  it('generates a take, lists it, reuses its seed, and keeps it', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.designGenerate).mockResolvedValue({ file: 'live_tmp/t1.wav', seed: 4242, cfg: 2, timesteps: 10, seconds: 4.1, description: 'A calm woman.', text: 'Sample.' })
    vi.mocked(api.designKeep).mockResolvedValue({ cand: 'c6.wav' })
    const { ctx, w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.designGenerate).mock.calls[0][0]).toBe('muaran')
    expect(w.text()).toContain('4242')
    await w.find('[data-seed-chip]').trigger('click')
    expect((w.find('input[data-seed]').element as HTMLInputElement).value).toBe('4242')
    await w.find('[data-keep]').trigger('click')
    await flushPromises()
    expect(api.designKeep).toHaveBeenCalledWith('muaran', expect.objectContaining({ file: 'live_tmp/t1.wav', seed: 4242 }))
    expect(ctx.load).toHaveBeenCalled()
  })

  it('shows the error and keeps earlier takes when generation fails', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.designGenerate).mockRejectedValue(new Error('model backend is not running'))
    const { w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('model backend is not running')
  })

  it('saves the description on blur', async () => {
    const { w } = mountPanel()
    const ta = w.find('textarea')
    await ta.setValue('A gruff man.')
    await ta.trigger('blur')
    expect(api.designDescription).toHaveBeenCalledWith('muaran', 'A gruff man.')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/components/source`
Expected: FAIL, components not found.

- [ ] **Step 3: Implement**

`src/components/source/CandidateRanker.vue`:

```vue
<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import type { Candidate, Verdict } from '../../api/types'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'
import { moveItem } from '../../utils/order'
import EmptyState from '../shared/EmptyState.vue'
import StarRating from '../shared/StarRating.vue'

const ACCENTS = ['british', 'american', 'other'] as const
const props = defineProps<{ candidates: Candidate[]; order: string[] }>()
const emit = defineEmits<{ reorder: [order: string[]]; verdict: [v: { cand: string } & Verdict] }>()
const { play } = useAudioPlayer()
const ctx = inject(SPEAKER_CTX_KEY, null)   // absent when the ranker is mounted on its own (tests)

const isSource = (id: string) => ctx?.selectedSources.value.has(`cand:${id}`) ?? false
function toggleSource(id: string, on: boolean) {
  if (!ctx) return
  const next = new Set(ctx.selectedSources.value)
  on ? next.add(`cand:${id}`) : next.delete(`cand:${id}`)
  ctx.selectedSources.value = next
}

const rows = computed(() => {
  const ranked = props.order.filter((id) => props.candidates.some((c) => c.id === id))
  const byId = new Map(props.candidates.map((c) => [c.id, c]))
  return [...ranked.map((id) => byId.get(id)!), ...props.candidates.filter((c) => !ranked.includes(c.id))]
})
const ids = computed(() => rows.value.map((c) => c.id))
const dragFrom = ref<number | null>(null)

function move(from: number, to: number) {
  if (to < 0 || to >= ids.value.length || from === to) return
  emit('reorder', moveItem(ids.value, from, to))
}
function drop(to: number) {
  if (dragFrom.value !== null) move(dragFrom.value, to)
  dragFrom.value = null
}
</script>

<template>
  <EmptyState v-if="!rows.length" message="No candidates yet. Generate one above." />
  <div
    v-for="(c, i) in rows"
    :key="c.id"
    class="cand"
    :class="{ picked: i === 0 && order.length }"
    draggable="true"
    @dragstart="dragFrom = i"
    @dragover.prevent
    @drop.prevent="drop(i)"
  >
    <span class="grip" title="drag to rank">⠇</span>
    <input v-if="ctx" type="checkbox" data-source title="use as a clone source" :checked="isSource(c.id)" @change="toggleSource(c.id, ($event.target as HTMLInputElement).checked)" />
    <b class="rank">{{ i + 1 }}.</b>
    <button class="play" @click="play(c.file)">▶</button>
    <span>{{ c.id.replace('.wav', '') }}</span>
    <span v-if="c.scores" class="chip" :class="c.scores.p_us > 0.5 ? 'us' : 'good'">p_us {{ c.scores.p_us.toFixed(2) }}</span>
    <span v-if="c.gen?.seed !== undefined" class="chip">seed {{ c.gen.seed }}</span>
    <span v-else class="chip warn" data-no-seed title="made before seeds were recorded; the WAV is the only copy">no recorded seed</span>
    <span class="grow" />
    <button v-for="a in ACCENTS" :key="a" :data-accent="a" :class="{ on: c.verdict.accent === a }" @click="emit('verdict', { cand: c.id, accent: a })">{{ a }}</button>
    <StarRating :model-value="c.verdict.fit ?? 0" @update:model-value="emit('verdict', { cand: c.id, fit: $event })" />
    <button data-reject :class="{ on: c.verdict.reject }" @click="emit('verdict', { cand: c.id, reject: !c.verdict.reject })">reject</button>
    <button data-move="up" :disabled="i === 0" aria-label="move up" @click="move(i, i - 1)">↑</button>
    <button data-move="down" :disabled="i === rows.length - 1" aria-label="move down" @click="move(i, i + 1)">↓</button>
  </div>
</template>

<style scoped>
.cand { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; padding: 6px 0; border-top: 1px solid var(--line); }
.cand.picked:first-of-type { outline: 2px solid var(--ok); outline-offset: -2px; }
.grip { cursor: grab; color: var(--dim); }
.rank { color: var(--acc); }
.grow { flex: 1; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); }
.chip.us { border-color: var(--bad); color: var(--bad); }
.chip.good { border-color: var(--ok); color: var(--ok); }
.chip.warn { border-color: #f0b400; color: #f0b400; }
button.on { background: var(--acc); color: #fff; border-color: var(--acc); }
</style>
```

Notes for the executor: with `order` empty the first row has no green outline (nothing ranked); `.picked` is applied to the first row only when an order exists. In the first test, `rows[0]` after `order=['c1.wav']` is `c1`, as asserted. In the "moves a candidate down" test with an empty order, `ids` is `[c0, c1, c2]`, so moving index 0 down gives `[c1, c0, c2]`.

`src/components/source/RealClipList.vue`:

```vue
<script setup lang="ts">
import type { RealClip } from '../../api/types'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import EmptyState from '../shared/EmptyState.vue'

defineProps<{ clips: RealClip[] }>()
const ctx = useSpeakerContext()
const { play } = useAudioPlayer()

function toggle(id: string, on: boolean) {
  const next = new Set(ctx.selectedSources.value)
  on ? next.add(`real:${id}`) : next.delete(`real:${id}`)
  ctx.selectedSources.value = next
}
</script>

<template>
  <EmptyState v-if="!clips.length" message="No real clips for this speaker." />
  <div v-for="c in clips" :key="c.id" class="clip">
    <input type="checkbox" :checked="ctx.selectedSources.value.has(`real:${c.id}`)" @change="toggle(c.id, ($event.target as HTMLInputElement).checked)" />
    <button class="play" @click="play(c.wav)">▶</button>
    <div>
      <span class="chip" :class="{ on: c.curated_rank }">{{ c.curated_rank ? `curated #${c.curated_rank}` : 'uncurated' }}</span>
      <span class="chip">{{ c.duration.toFixed(1) }}s</span>
      <span v-if="c.noise_db !== null" class="chip">noise {{ c.noise_db }} dB</span>
      <span class="chip">{{ c.id }}</span>
      <div class="dim">{{ c.text.slice(0, 200) }}</div>
    </div>
  </div>
</template>

<style scoped>
.clip { display: grid; grid-template-columns: 22px 30px 1fr; gap: 6px; padding: 6px 0; border-top: 1px solid var(--line); align-items: start; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); margin-right: 4px; }
.chip.on { border-color: var(--acc); color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

`src/components/source/SuppliedClip.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useSpeakerContext } from '../../composables/useSpeakerContext'

const ctx = useSpeakerContext()
const wav = ref('')
const text = ref('')
function add() {
  if (!wav.value.trim()) return
  ctx.addSupplied(wav.value.trim(), text.value.trim())
  wav.value = text.value = ''
}
</script>

<template>
  <div class="supplied">
    <input v-model="wav" placeholder="other source wav, e.g. data/… .wav" />
    <input v-model="text" placeholder="its transcript" />
    <button @click="add">Add as source</button>
  </div>
</template>

<style scoped>
.supplied { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
.supplied input { flex: 1; min-width: 200px; }
</style>
```

`src/components/source/DesignPanel.vue`:

```vue
<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../../api/client'
import type { LiveTake } from '../../api/types'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useModelStore } from '../../stores/model'
import CandidateRanker from './CandidateRanker.vue'

const DEFAULT_CFG = 2
const DEFAULT_STEPS = 10
const ctx = useSpeakerContext()
const model = useModelStore()
const { play } = useAudioPlayer()

const description = ref(ctx.detail.value?.design?.description ?? '')
// ctx.load() replaces the detail after Keep, verdicts and reorders; keep the box in step with the saved description.
watch(() => ctx.detail.value?.design?.description, (d) => { if (d !== undefined) description.value = d })
const seed = ref('')
const cfg = ref(DEFAULT_CFG)
const steps = ref(DEFAULT_STEPS)
const busy = ref(false)
const error = ref('')
const takes = ref<LiveTake[]>([])

async function generate() {
  busy.value = true
  error.value = ''
  try {
    takes.value.unshift(await api.designGenerate(ctx.slug, { description: description.value, seed: seed.value.trim(), cfg: cfg.value, timesteps: steps.value }))
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
async function keep(t: LiveTake) {
  await api.designKeep(ctx.slug, t)
  takes.value = takes.value.filter((x) => x !== t)
  await ctx.load()
}
const saveDescription = () => api.designDescription(ctx.slug, description.value)
async function verdict(v: Parameters<typeof api.designVerdict>[1]) {
  await api.designVerdict(ctx.slug, v)
  await ctx.load()
}
async function reorder(order: string[]) {
  await api.designOrder(ctx.slug, order)
  await ctx.load()
}
</script>

<template>
  <div v-if="ctx.detail.value?.design">
    <textarea v-model="description" rows="2" @blur="saveDescription" />
    <div class="live">
      <b>Live design</b>
      seed <input data-seed v-model="seed" placeholder="random" />
      cfg <input type="number" step="0.5" v-model.number="cfg" />
      steps <input type="number" v-model.number="steps" />
      <button data-generate class="primary" :disabled="!model.ready || busy" :title="model.reason" @click="generate">{{ busy ? 'generating…' : 'Generate' }}</button>
      <span v-if="!model.ready" class="dim">{{ model.reason }}</span>
      <span v-if="error" class="err">{{ error }}</span>
      <div v-for="t in takes" :key="t.file" class="take">
        <button class="play" @click="play(`data/voice_design/${t.file}`)">▶</button>
        <button data-seed-chip class="chip" title="reuse this seed" @click="seed = String(t.seed)">seed {{ t.seed }}</button>
        <span class="dim">cfg {{ t.cfg }} · {{ t.timesteps }} steps · {{ t.seconds }}s</span>
        <button data-keep @click="keep(t)">Keep</button>
      </div>
    </div>
    <CandidateRanker :candidates="ctx.detail.value.design.candidates" :order="ctx.detail.value.design.order" @reorder="reorder" @verdict="verdict" />
  </div>
</template>

<style scoped>
textarea { width: 100%; }
.live { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; margin: 8px 0; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.live input { width: 84px; }
.take { width: 100%; display: flex; gap: 8px; align-items: center; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border-radius: 10px; padding: 0 8px; font-size: 12px; color: var(--acc); cursor: pointer; }
.primary { background: var(--acc); color: #fff; border-color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); font-size: 13px; }
</style>
```

`src/components/source/SourcePanel.vue`:

```vue
<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import SectionCard from '../shared/SectionCard.vue'
import DesignPanel from './DesignPanel.vue'
import RealClipList from './RealClipList.vue'
import SuppliedClip from './SuppliedClip.vue'

const ctx = useSpeakerContext()
</script>

<template>
  <SectionCard title="1. Source">
    <p class="dim">Tick the clip(s) to clone from. Several ticked clips are compared on the same lines with the same seed.</p>
    <RealClipList v-if="ctx.detail.value && (ctx.detail.value.summary.origin === 'real' || ctx.detail.value.clips.length)" :clips="ctx.detail.value.clips" />
    <DesignPanel v-if="ctx.detail.value?.design" />
    <SuppliedClip />
  </SectionCard>
</template>

<style scoped>
.dim { color: var(--dim); font-size: 12px; }
</style>
```

Modify `SpeakerView.vue`: replace the comment line with `<SourcePanel />` and import it.

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass; type check clean.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)

- [ ] **Step 6: Milestone M1, stop and show the user**

The audition loop now works with the model off: speakers list, real and designed sources, the ranker with verdicts and drag/keyboard ordering, all writing the existing `audit.json`; "Register pick" copies a rank-1 candidate into the prompt bank.

**Prerequisites for M1:** Tasks 1 to 6 (the Python server) and Tasks 7 to 12 (the web app) are all done. `run.sh` does not exist until Task 15, so start it by hand:

```bash
cd tools/studio/web && npm run build
cd ../server && python3 -m studio_server --port 8930
```

Then tell the user it is ready to audition the 12 pilot voices at http://127.0.0.1:8930/speakers. **Pause here**: do not start Task 13 until the user has listened and reported, because their verdict on the designed voices gates the whole voiceless-NPC track. Before handing over, remind them that rankings and verdicts are written to the real `data/voice_design/audit.json` and that "Register pick" writes to the prompt bank.
