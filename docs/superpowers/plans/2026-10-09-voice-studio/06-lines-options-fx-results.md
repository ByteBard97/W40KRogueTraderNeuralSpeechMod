# Voice Studio first slice, part 6 of 7: Lines, options, FX and results

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Tasks 13 to 14. Vue app: test lines, model options, post-processing, generation and results.
**Previous part:** [Source section (milestone M1)](05-source-section-m1.md). **Next part:** [Integration and verification](07-integration.md).

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

### Task 13: Test-lines section and model options section

**Files:**
- Create: `src/components/lines/LinePanel.vue`, `src/components/options/OptionsPanel.vue`, `src/utils/spread.ts`
- Modify: `src/views/SpeakerView.vue` (render both)
- Tests: `src/components/lines/LinePanel.test.ts`, `src/components/options/OptionsPanel.test.ts`, `src/utils/spread.test.ts`

**Interfaces:**
- Consumes: speaker context (`lines`, `selectedLines`, `options`).
- Produces:
  - `<LinePanel />`: search input, emotion filter chips (derived from `lines`), "Pick 6 spread across emotions" and "Clear" buttons, a checkbox list (cap `LINE_RENDER_CAP = 200` with a "Show 200 more" button), a play button for the bank clip (disabled with title when `baseline` is null), emotion/pace chips and the line's annotation style. Empty state "No lines for this speaker." `spreadPick(lines: Line[], n = 6): string[]` is exported from `src/utils/spread.ts`: groups by emotion, takes the middle line, longer than 50 and shorter than 220 characters, from each of the largest emotion groups until `n` are chosen (never duplicates, `[]` for no eligible lines).
  - `<OptionsPanel />`: v-model-style editing of `ctx.options` (cfg, timesteps, seed, use_instruct, retry_badcase, normalize, continuation) with the continuation caveat text.

- [ ] **Step 1: Write the failing tests**

`src/utils/spread.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Line } from '../api/types'
import { spreadPick } from './spread'

const L = (guid: string, emotion: string | null, len = 80): Line => ({ guid, text: 'x'.repeat(len), emotion, intensity: null, pace: null, instruct: null, baseline: null })

describe('spreadPick', () => {
  it('takes one mid-length line from each of the largest emotion groups', () => {
    const lines = [L('a1', 'calm'), L('a2', 'calm'), L('a3', 'calm'), L('b1', 'sad'), L('b2', 'sad'), L('c1', 'angry')]
    const pick = spreadPick(lines, 2)
    expect(pick).toHaveLength(2)
    expect(new Set(pick.map((g) => lines.find((l) => l.guid === g)!.emotion))).toEqual(new Set(['calm', 'sad']))
  })
  it('skips too-short and too-long lines and handles empty or null emotions', () => {
    expect(spreadPick([L('s', 'calm', 10), L('l', 'calm', 500)], 6)).toEqual([])
    expect(spreadPick([], 6)).toEqual([])
    expect(spreadPick([L('n', null)], 6)).toEqual(['n'])
  })
  it('never returns more than n or duplicates', () => {
    const lines = Array.from({ length: 20 }, (_, i) => L(`g${i}`, `e${i}`))
    const pick = spreadPick(lines, 6)
    expect(pick).toHaveLength(6)
    expect(new Set(pick).size).toBe(6)
  })
})
```

`src/components/lines/LinePanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import LinePanel from './LinePanel.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const mk = (n: number) => ({ guid: `g${n}`, text: `line number ${n} `.repeat(6), emotion: n % 2 ? 'calm' : 'sad', intensity: 0.2, pace: 'normal', instruct: null, baseline: n === 0 ? null : `data/r/g${n}.wav` })

function mountWith(count: number) {
  const ctx = { lines: ref(Array.from({ length: count }, (_, i) => mk(i))), selectedLines: ref(new Set<string>()) }
  return { ctx, w: mount(LinePanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('LinePanel', () => {
  it('ticks a line into the selection', async () => {
    const { ctx, w } = mountWith(4)
    await w.findAll('input[type=checkbox]')[1].setValue(true)
    expect([...ctx.selectedLines.value]).toEqual(['g1'])
  })

  it('filters by emotion chip and by search text', async () => {
    const { w } = mountWith(6)
    await w.find('[data-emo="sad"]').trigger('click')
    expect(w.findAll('.line')).toHaveLength(3)
    await w.find('input[type=search]').setValue('number 2')
    expect(w.findAll('.line')).toHaveLength(1)
  })

  it('caps rendering and shows more on request', async () => {
    const { w } = mountWith(450)
    expect(w.findAll('.line')).toHaveLength(200)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.line')).toHaveLength(400)
  })

  it('"spread" selects up to 6 lines and "clear" empties the selection', async () => {
    const { ctx, w } = mountWith(30)
    await w.find('[data-spread]').trigger('click')
    expect(ctx.selectedLines.value.size).toBeGreaterThan(0)
    expect(ctx.selectedLines.value.size).toBeLessThanOrEqual(6)
    await w.find('[data-clear]').trigger('click')
    expect(ctx.selectedLines.value.size).toBe(0)
  })

  it('disables the bank play button when there is no bank clip and shows an empty state', () => {
    const { w } = mountWith(2)
    expect(w.findAll('.play')[0].attributes('disabled')).toBeDefined()
    const empty = mount(LinePanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: { lines: ref([]), selectedLines: ref(new Set()) } } } })
    expect(empty.text()).toContain('No lines for this speaker')
  })
})
```

`src/components/options/OptionsPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import OptionsPanel from './OptionsPanel.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'
import { DEFAULT_OPTIONS } from '../../composables/useSpeakerState'

describe('OptionsPanel', () => {
  it('edits the shared options object', async () => {
    const ctx = { options: ref({ ...DEFAULT_OPTIONS }) }
    const w = mount(OptionsPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.find('input[data-cfg]').setValue('3.5')
    await w.find('input[data-seed]').setValue('77')
    await w.find('input[data-continuation]').setValue(true)
    expect(ctx.options.value).toMatchObject({ cfg: 3.5, seed: '77', continuation: true })
    expect(w.text()).toMatch(/echo the reference/i)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/utils/spread.test.ts src/components/lines src/components/options`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement**

`src/utils/spread.ts`:

```ts
import type { Line } from '../api/types'

const MIN_CHARS = 50
const MAX_CHARS = 220

export function spreadPick(lines: Line[], n = 6): string[] {
  const groups = new Map<string, Line[]>()
  for (const l of lines) {
    if (l.text.length <= MIN_CHARS || l.text.length >= MAX_CHARS) continue
    const k = l.emotion ?? ''
    groups.set(k, [...(groups.get(k) ?? []), l])
  }
  return [...groups.values()]
    .sort((a, b) => b.length - a.length)
    .slice(0, n)
    .map((g) => g[Math.floor(g.length / 2)].guid)
}
```

`src/components/lines/LinePanel.vue`:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { spreadPick } from '../../utils/spread'
import EmptyState from '../shared/EmptyState.vue'

const LINE_RENDER_CAP = 200
const ctx = useSpeakerContext()
const { play } = useAudioPlayer()
const query = ref('')
const emotion = ref<string | null>(null)
const shown = ref(LINE_RENDER_CAP)

const emotions = computed(() => [...new Set(ctx.lines.value.map((l) => l.emotion).filter((e): e is string => !!e))].sort())
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return ctx.lines.value.filter((l) => (!emotion.value || l.emotion === emotion.value) && (!q || l.text.toLowerCase().includes(q)))
})
const visible = computed(() => filtered.value.slice(0, shown.value))

function toggle(guid: string, on: boolean) {
  const next = new Set(ctx.selectedLines.value)
  on ? next.add(guid) : next.delete(guid)
  ctx.selectedLines.value = next
}
const spread = () => (ctx.selectedLines.value = new Set(spreadPick(ctx.lines.value)))
const clear = () => (ctx.selectedLines.value = new Set())
</script>

<template>
  <EmptyState v-if="!ctx.lines.value.length" message="No lines for this speaker." />
  <div v-else>
    <div class="tools">
      <input type="search" v-model="query" placeholder="search text" />
      <button data-emo="" :class="{ on: !emotion }" @click="emotion = null">all</button>
      <button v-for="e in emotions" :key="e" :data-emo="e" :class="{ on: emotion === e }" @click="emotion = e">{{ e }}</button>
      <button data-spread @click="spread">Pick 6 spread across emotions</button>
      <button data-clear @click="clear">Clear</button>
      <span class="dim">{{ filtered.length }} lines, {{ ctx.selectedLines.value.size }} ticked</span>
    </div>
    <div v-for="l in visible" :key="l.guid" class="line">
      <input type="checkbox" :checked="ctx.selectedLines.value.has(l.guid)" @change="toggle(l.guid, ($event.target as HTMLInputElement).checked)" />
      <button class="play" :disabled="!l.baseline" :title="l.baseline ? 'the bank render of this line' : 'no bank render'" @click="l.baseline && play(l.baseline)">▶</button>
      <div>
        <span class="chip">{{ l.emotion ?? '—' }} {{ l.intensity ?? '' }}</span><span class="chip">{{ l.pace ?? '—' }}</span>
        <div>{{ l.text }}</div>
        <div v-if="l.instruct" class="dim">style: {{ l.instruct }}</div>
      </div>
    </div>
    <button v-if="filtered.length > shown" data-more @click="shown += LINE_RENDER_CAP">Show {{ LINE_RENDER_CAP }} more</button>
  </div>
</template>

<style scoped>
.tools { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.tools .on { background: var(--acc); color: #fff; border-color: var(--acc); }
.line { display: grid; grid-template-columns: 22px 30px 1fr; gap: 6px; padding: 6px 0; border-top: 1px solid var(--line); align-items: start; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); margin-right: 4px; }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

`src/components/options/OptionsPanel.vue`:

```vue
<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'

const ctx = useSpeakerContext()
</script>

<template>
  <div class="grid">
    <label>cfg <input data-cfg type="number" step="0.5" v-model.number="ctx.options.value.cfg" /></label>
    <label>timesteps <input data-timesteps type="number" v-model.number="ctx.options.value.timesteps" /></label>
    <label>seed <input data-seed v-model="ctx.options.value.seed" placeholder="blank = new random per line" /> <span class="dim">a typed value pins every line</span></label>
    <label><input type="checkbox" v-model="ctx.options.value.use_instruct" /> use the line's annotation style as a prefix</label>
    <label><input type="checkbox" v-model="ctx.options.value.retry_badcase" /> retry bad takes</label>
    <label><input type="checkbox" v-model="ctx.options.value.normalize" /> normalize text</label>
    <label><input data-continuation type="checkbox" v-model="ctx.options.value.continuation" /> continuation: also pass the transcript as a prompt</label>
  </div>
  <p class="dim">Continuation can echo the reference audio at the start of the output; the bank was rendered with it off. One seed is used per line and shared by every ticked source.</p>
</template>

<style scoped>
.grid { display: grid; gap: 6px; }
label { display: flex; gap: 8px; align-items: center; }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

Modify `SpeakerView.vue`: after `<SourcePanel />` add `<SectionCard title="2. Test lines"><LinePanel /></SectionCard>` and `<SectionCard title="3. Model options"><OptionsPanel /></SectionCard>` (import both and `SectionCard`).

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass; type check clean.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)

---

### Task 14: Post-processing, generation and results

**Files:**
- Create: `src/components/fx/FxPanel.vue`, `src/components/results/{ResultsPanel,TakeRow}.vue`
- Modify: `src/views/SpeakerView.vue` (render FX and Results; add the Generate bar)
- Tests: `src/components/results/TakeRow.test.ts`, `src/components/results/ResultsPanel.test.ts`, `src/components/fx/FxPanel.test.ts`

**Interfaces:**
- Consumes: speaker context, `runBatch`, `api`, `useModelStore`, `ClipCompare`, `StarRating`.
- Produces:
  - `<FxPanel />`: multi-select of `ctx.fxAvailable` bound to `ctx.fxChosen` (order of selection = order of application; show the order), note that the real clips are already processed, link "Open FX Lab" to `http://127.0.0.1:8908` (new tab), and empty state "No FX presets found." when the list is empty.
  - `<TakeRow :take="Take" :line="Line | null" />`: `ClipCompare` with clips `source clip` (take.reference, the real or designed clip it was cloned from), `bank` (line.baseline), `raw clone` (take.raw), `fx` (take.fx?.wav plus `?v=`), plus source label, seed, cfg, steps, audio seconds, `StarRating` (calls `api.takeRate` then `ctx.upsertTake`), and an "apply FX" / "re-apply FX" button (calls `api.takeFx(slug, id, presets)` where presets are the picker's, or the take's own when the picker is empty; error text shown in the row; disabled when there is nothing to apply).
  - `<ResultsPanel />`: Generate bar (`Generate N takes` button where `N = chosenSources × selectedLines`, disabled with `model.reason` unless ready, disabled with a hint when nothing is selected; progress text `generating i / n`; Stop button; error banner) and takes grouped by line (newest group first), each group showing the line text. After each take, if `ctx.fxChosen` is non-empty the take gets FX applied automatically. Empty state "No takes yet. Tick a source and some lines, then Generate."

- [ ] **Step 1: Write the failing tests**

`src/components/results/TakeRow.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))
vi.mock('../../api/client', () => ({ api: { takeRate: vi.fn(), takeFx: vi.fn() } }))

import TakeRow from './TakeRow.vue'

const take = (over = {}) => ({
  id: 't1', raw: 'data/raw.wav', text: 'Hi.', guid: 'g1', reference: 'data/voices/wav/Pasqal/E1.wav',
  options: { cfg: 2, timesteps: 10 }, instruct: null, seed: 55, seconds: 3.2, audio_s: 2.5, rating: 0, note: '', fx: null, ...over,
})
const line = { guid: 'g1', baseline: 'data/render/export/wav/g1.wav' }

function mountRow(t = take(), fxChosen: string[] = []) {
  const ctx = { slug: 'pasqal', fxChosen: ref(fxChosen), upsertTake: vi.fn() }
  return { ctx, w: mount(TakeRow, { props: { take: t as never, line: line as never }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('TakeRow', () => {
  beforeEach(() => vi.clearAllMocks())

  it('offers bank, raw and fx clips and shows seed and source', () => {
    const { w } = mountRow(take({ fx: { presets: ['Clean'], wav: 'data/studio/pasqal/fx/t1.wav', v: 9 } }))
    expect(w.text()).toContain('seed 55')
    expect(w.text()).toContain('E1')
    const labels = w.findAll('.clip').map((b) => b.text())
    expect(labels).toEqual(expect.arrayContaining(['source clip', 'bank', 'raw clone', 'fx']))
  })

  it('re-apply with an empty picker repeats the take\'s own presets instead of clearing the FX', async () => {
    vi.mocked(api.takeFx).mockResolvedValue(take() as never)
    const { w } = mountRow(take({ fx: { presets: ['Servitor', 'Clean'], wav: 'data/studio/pasqal/fx/t1.wav', v: 9 } }), [])
    expect(w.find('[data-fx]').attributes('disabled')).toBeUndefined()
    await w.find('[data-fx]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', ['Servitor', 'Clean'])
  })

  it('rates a take through the api and updates the context', async () => {
    vi.mocked(api.takeRate).mockResolvedValue(take({ rating: 4 }) as never)
    const { ctx, w } = mountRow()
    await w.findAll('.star')[3].trigger('click')
    await flushPromises()
    expect(api.takeRate).toHaveBeenCalledWith('pasqal', 't1', { rating: 4 })
    expect(ctx.upsertTake).toHaveBeenCalled()
  })

  it('applies FX with the chosen presets and shows an error from the server', async () => {
    vi.mocked(api.takeFx).mockRejectedValue(new Error('tools/fx_lab/.venv-fx is missing'))
    const { w } = mountRow(take(), ['Clean'])
    await w.find('[data-fx]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', ['Clean'])
    expect(w.text()).toContain('.venv-fx is missing')
  })

  it('disables apply when no preset is chosen and the take has no fx', () => {
    const { w } = mountRow()
    expect(w.find('[data-fx]').attributes('disabled')).toBeDefined()
  })
})
```

`src/components/results/ResultsPanel.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { useModelStore } from '../../stores/model'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'
import { DEFAULT_OPTIONS } from '../../composables/useSpeakerState'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))
vi.mock('../../api/client', () => ({ api: { cloneGenerate: vi.fn(), takeFx: vi.fn(), takeRate: vi.fn() } }))

import ResultsPanel from './ResultsPanel.vue'

const lines = [{ guid: 'g1', text: 'Greetings.', instruct: null, baseline: null }, { guid: 'g2', text: 'Farewell.', instruct: null, baseline: null }]
const src = { key: 'real:E1', label: 'E1', wav: 'data/v/E1.wav', text: 'Hello.', origin: 'real' }

function mountPanel(over: Record<string, unknown> = {}) {
  const takes = ref<unknown[]>([])
  const ctx = {
    slug: 'pasqal', lines: ref(lines), takes, options: ref({ ...DEFAULT_OPTIONS }), fxChosen: ref<string[]>([]),
    selectedLines: ref(new Set(['g1', 'g2'])), chosenSources: computed(() => [src]),
    upsertTake: (t: unknown) => takes.value.unshift(t), ...over,
  }
  return { ctx, w: mount(ResultsPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('ResultsPanel', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('shows an empty state and a disabled generate while the model is down', () => {
    const { w } = mountPanel()
    expect(w.text()).toContain('No takes yet')
    expect(w.find('[data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/not running/i)
  })

  it('generates sources x lines and shows progress and the count on the button', async () => {
    useModelStore().state = 'ready'
    let n = 0
    vi.mocked(api.cloneGenerate).mockImplementation(async () => ({ id: `t${++n}`, guid: `g${n}`, text: `x${n}`, raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: n, rating: 0, fx: null } as never))
    const { w } = mountPanel()
    expect(w.find('[data-generate]').text()).toContain('2')
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(api.cloneGenerate).toHaveBeenCalledTimes(2)
    expect(w.text()).toContain('done, 2 takes')
  })

  it('applies chosen FX automatically after each take', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.cloneGenerate).mockResolvedValue({ id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: null } as never)
    vi.mocked(api.takeFx).mockResolvedValue({ id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: { presets: ['Clean'], wav: 'w', v: 1 } } as never)
    const { w } = mountPanel({ fxChosen: ref(['Clean']), selectedLines: ref(new Set(['g1'])) })
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', ['Clean'])
  })

  it('stops on a backend error, shows it, and keeps takes already made', async () => {
    useModelStore().state = 'ready'
    let n = 0
    vi.mocked(api.cloneGenerate).mockImplementation(async () => {
      if (++n === 2) throw new Error('model backend is not running')
      return { id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: null } as never
    })
    const { ctx, w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('model backend is not running')
    expect(ctx.takes.value).toHaveLength(1)
  })

  it('disables generate with a hint when no source or no line is selected', () => {
    useModelStore().state = 'ready'
    const { w } = mountPanel({ selectedLines: ref(new Set()) })
    expect(w.find('[data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/tick a source and some lines/i)
  })
})
```

`src/components/fx/FxPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import FxPanel from './FxPanel.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

describe('FxPanel', () => {
  it('toggles presets in selection order', async () => {
    const ctx = { fxAvailable: ref(['Clean', 'Servitor']), fxChosen: ref<string[]>([]) }
    const w = mount(FxPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.find('[data-fx="Servitor"]').trigger('click')
    await w.find('[data-fx="Clean"]').trigger('click')
    expect(ctx.fxChosen.value).toEqual(['Servitor', 'Clean'])
    expect(w.text()).toContain('1. Servitor')
    await w.find('[data-fx="Servitor"]').trigger('click')
    expect(ctx.fxChosen.value).toEqual(['Clean'])
  })

  it('shows an empty state with no presets', () => {
    const ctx = { fxAvailable: ref<string[]>([]), fxChosen: ref<string[]>([]) }
    const w = mount(FxPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    expect(w.text()).toContain('No FX presets found')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/components/results src/components/fx`
Expected: FAIL, components not found.

- [ ] **Step 3: Implement**

`src/components/fx/FxPanel.vue`:

```vue
<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import EmptyState from '../shared/EmptyState.vue'

const FX_LAB_URL = 'http://127.0.0.1:8908'
const ctx = useSpeakerContext()

function toggle(name: string) {
  const cur = ctx.fxChosen.value
  ctx.fxChosen.value = cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]
}
</script>

<template>
  <EmptyState v-if="!ctx.fxAvailable.value.length" message="No FX presets found." />
  <div v-else>
    <p class="dim">
      Presets run in the order you pick them, on the raw clone. The real clips are often already processed, so a clone from one may be processed twice.
      Tune the presets themselves in the <a :href="FX_LAB_URL" target="_blank" rel="noopener">FX Lab</a>.
    </p>
    <div class="presets">
      <button v-for="n in ctx.fxAvailable.value" :key="n" :data-fx="n" :class="{ on: ctx.fxChosen.value.includes(n) }" @click="toggle(n)">
        {{ ctx.fxChosen.value.includes(n) ? `${ctx.fxChosen.value.indexOf(n) + 1}. ` : '' }}{{ n }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.presets { display: flex; gap: 6px; flex-wrap: wrap; }
.on { background: var(--acc); color: #fff; border-color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
</style>
```

`src/components/results/TakeRow.vue`:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../../api/client'
import type { Line, Take } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import ClipCompare from '../shared/ClipCompare.vue'
import StarRating from '../shared/StarRating.vue'

const props = defineProps<{ take: Take; line: Line | null }>()
const ctx = useSpeakerContext()
const error = ref('')
const busy = ref(false)

const clips = computed(() => [
  { key: 'source', label: 'source clip', path: props.take.reference },
  { key: 'bank', label: 'bank', path: props.line?.baseline ?? null },
  { key: 'raw', label: 'raw clone', path: props.take.raw },
  { key: 'fx', label: 'fx', path: props.take.fx ? `${props.take.fx.wav}?v=${props.take.fx.v}` : null },
])
const source = computed(() => (props.take.reference.split('/').pop() ?? '').replace('.wav', ''))
// The picker wins; with an empty picker, "re-apply" repeats the take's own presets. An empty list would clear the FX.
const presetsToApply = computed(() => (ctx.fxChosen.value.length ? ctx.fxChosen.value : props.take.fx?.presets ?? []))
const canApply = computed(() => presetsToApply.value.length > 0)

async function rate(n: number) {
  ctx.upsertTake(await api.takeRate(ctx.slug, props.take.id, { rating: n }))
}
async function applyFx() {
  busy.value = true
  error.value = ''
  try {
    ctx.upsertTake(await api.takeFx(ctx.slug, props.take.id, presetsToApply.value))
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="take">
    <ClipCompare :clips="clips" />
    <button data-fx :disabled="!canApply || busy" @click="applyFx">{{ take.fx ? 're-apply FX' : 'apply FX' }}</button>
    <span class="dim">{{ source }} · seed {{ take.seed }} · cfg {{ take.options.cfg }} · {{ take.options.timesteps }} steps · {{ take.audio_s ?? '?' }}s audio</span>
    <StarRating :model-value="take.rating" @update:model-value="rate" />
    <span v-if="error" class="err">{{ error }}</span>
  </div>
</template>

<style scoped>
.take { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 4px 0; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); font-size: 13px; }
</style>
```

`src/components/results/ResultsPanel.vue`:

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../../api/client'
import type { Take } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useModelStore } from '../../stores/model'
import { runBatch } from '../../utils/batch'
import EmptyState from '../shared/EmptyState.vue'
import TakeRow from './TakeRow.vue'

const ctx = useSpeakerContext()
const model = useModelStore()
const running = ref(false)
const stopRequested = ref(false)
const progress = ref('')
const error = ref('')

const chosenLines = computed(() => ctx.lines.value.filter((l) => ctx.selectedLines.value.has(l.guid)))
const total = computed(() => chosenLines.value.length * ctx.chosenSources.value.length)
const hint = computed(() => (total.value ? '' : 'Tick a source and some lines first.'))

const groups = computed(() => {
  const by = new Map<string, Take[]>()
  for (const t of ctx.takes.value) by.set(t.guid ?? t.text, [...(by.get(t.guid ?? t.text) ?? []), t])
  return [...by.entries()].map(([key, takes]) => ({ key, takes, line: ctx.lines.value.find((l) => l.guid === key) ?? null }))
})

async function generate() {
  running.value = true
  stopRequested.value = false
  error.value = ''
  let i = 0
  const res = await runBatch({
    lines: chosenLines.value,
    sources: ctx.chosenSources.value,
    options: ctx.options.value,
    shouldStop: () => stopRequested.value,
    generate: (req) => {
      progress.value = `generating ${++i} / ${total.value}…`
      return api.cloneGenerate(ctx.slug, req)
    },
    onTake: async (t) => {
      ctx.upsertTake(t)
      if (ctx.fxChosen.value.length) {
        try {
          ctx.upsertTake(await api.takeFx(ctx.slug, t.id, ctx.fxChosen.value))
        } catch (e) {
          error.value = e instanceof Error ? e.message : String(e)
        }
      }
    },
  })
  progress.value = `done, ${res.done} takes`
  if (res.error) error.value = res.error
  running.value = false
}
</script>

<template>
  <div>
    <div class="bar">
      <button data-generate class="primary" :disabled="!model.ready || running || !total" :title="model.reason || hint" @click="generate">
        Generate {{ total }} take{{ total === 1 ? '' : 's' }}
      </button>
      <button v-if="running" @click="stopRequested = true">Stop</button>
      <span class="dim">{{ progress }}</span>
      <span v-if="!model.ready" class="dim">{{ model.reason }}</span>
      <span v-else-if="hint" class="dim">{{ hint }}</span>
    </div>
    <p v-if="error" class="err">{{ error }}</p>
    <EmptyState v-if="!groups.length" message="No takes yet. Tick a source and some lines, then Generate." />
    <div v-for="g in groups" :key="g.key" class="group">
      <div class="text">{{ g.takes[0].text }}</div>
      <TakeRow v-for="t in g.takes" :key="t.id" :take="t" :line="g.line" />
    </div>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.primary { background: var(--acc); color: #fff; border-color: var(--acc); }
.group { border-top: 1px solid var(--line); padding: 8px 0; }
.text { margin-bottom: 4px; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); font-size: 13px; }
</style>
```

Modify `SpeakerView.vue`: add `<SectionCard title="4. Post-processing"><FxPanel /></SectionCard>` and `<SectionCard title="5. Results"><ResultsPanel /></SectionCard>` after the options card (import `FxPanel`, `ResultsPanel`).

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass; type check clean.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)
