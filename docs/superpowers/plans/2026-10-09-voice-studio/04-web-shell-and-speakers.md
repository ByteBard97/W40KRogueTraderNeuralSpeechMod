# Voice Studio first slice, part 4 of 7: Web shell, speakers list, speaker state

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Tasks 9 to 11. Vue app: audio player, shared components, app shell, speakers list, speaker context and profile bar.
**Previous part:** [Web foundation](03-web-foundation.md). **Next part:** [Source section (milestone M1)](05-source-section-m1.md).

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

### Task 9: Audio player, shared components and app shell

**Files:**
- Create: `src/composables/useAudioPlayer.ts`, `src/components/shared/{AppShell,ModelStatus,ClipCompare,StarRating,SectionCard,EmptyState}.vue`
- Modify: `src/App.vue` (use `AppShell`)
- Tests: `src/composables/useAudioPlayer.test.ts`, `src/components/shared/ClipCompare.test.ts`, `StarRating.test.ts`, `SectionCard.test.ts`

**Interfaces:**
- Consumes: `fileUrl`, `useModelStore`.
- Produces:
  - `useAudioPlayer()` (module singleton): `playing: Ref<string | null>` (the path playing), `play(path: string): void`, `stop(): void`; a second `play` of the same path toggles it off. One shared `HTMLAudioElement`.
  - `<ClipCompare :clips="ClipItem[]" />` where `ClipItem = { key: string; label: string; path: string | null }`; renders one play button per clip (disabled with title "no clip" when `path` is null); the playing one has class `is-playing`.
  - `<StarRating :model-value="n" @update:model-value />` (clicking the current value sets 0).
  - `<SectionCard title :collapsed-by-default? >` with default slot and `#actions` slot; header button toggles collapse.
  - `<EmptyState :message />`, `<ModelStatus />` (dot plus label from the model store), `<AppShell>` (top bar: "Voice Studio", nav link to Speakers, `ModelStatus`, `<slot/>`).

- [ ] **Step 1: Write the failing tests**

`src/composables/useAudioPlayer.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'

const audio = { src: '', play: vi.fn().mockResolvedValue(undefined), pause: vi.fn(), addEventListener: vi.fn() }
vi.stubGlobal('Audio', vi.fn(() => audio))

import { useAudioPlayer } from './useAudioPlayer'

describe('useAudioPlayer', () => {
  beforeEach(() => {
    audio.play.mockClear()
    audio.pause.mockClear()
    useAudioPlayer().stop()
  })

  it('plays a path through /file and tracks it', () => {
    const p = useAudioPlayer()
    p.play('data/a.wav')
    expect(audio.src).toContain('/file?p=data%2Fa.wav')
    expect(audio.play).toHaveBeenCalled()
    expect(p.playing.value).toBe('data/a.wav')
  })

  it('toggles off when the same path is played twice and switches when another is played', () => {
    const p = useAudioPlayer()
    p.play('data/a.wav')
    p.play('data/a.wav')
    expect(p.playing.value).toBeNull()
    p.play('data/a.wav')
    p.play('data/b.wav')
    expect(p.playing.value).toBe('data/b.wav')
  })
})
```

`src/components/shared/ClipCompare.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const play = vi.fn()
vi.mock('../../composables/useAudioPlayer', () => ({
  useAudioPlayer: () => ({ play, playing: 'data/b.wav' }),
}))

import ClipCompare from './ClipCompare.vue'

const clips = [
  { key: 'bank', label: 'bank', path: 'data/a.wav' },
  { key: 'raw', label: 'raw clone', path: 'data/b.wav' },
  { key: 'fx', label: 'fx', path: null },
]

describe('ClipCompare', () => {
  it('renders a labelled button per clip and plays on click', async () => {
    const w = mount(ClipCompare, { props: { clips } })
    const btns = w.findAll('button')
    expect(btns.map((b) => b.text())).toEqual(expect.arrayContaining(['bank', 'raw clone', 'fx']))
    await btns[0].trigger('click')
    expect(play).toHaveBeenCalledWith('data/a.wav')
  })

  it('disables clips with no path and marks the playing one', () => {
    const w = mount(ClipCompare, { props: { clips } })
    const btns = w.findAll('button')
    expect(btns[2].attributes('disabled')).toBeDefined()
    expect(btns[1].classes()).toContain('is-playing')
  })
})
```

`src/components/shared/StarRating.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StarRating from './StarRating.vue'

describe('StarRating', () => {
  it('emits the clicked star and clears when the current star is clicked again', async () => {
    const w = mount(StarRating, { props: { modelValue: 2 } })
    const stars = w.findAll('button')
    expect(stars).toHaveLength(5)
    await stars[3].trigger('click')
    expect(w.emitted('update:modelValue')![0]).toEqual([4])
    await stars[1].trigger('click')
    expect(w.emitted('update:modelValue')![1]).toEqual([0])
  })
})
```

`src/components/shared/SectionCard.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SectionCard from './SectionCard.vue'

describe('SectionCard', () => {
  it('shows content, collapses on header click, and can start collapsed', async () => {
    const w = mount(SectionCard, { props: { title: 'Source' }, slots: { default: '<p class="body">hi</p>' } })
    expect(w.find('.body').exists()).toBe(true)
    await w.find('.head').trigger('click')
    expect(w.find('.body').exists()).toBe(false)
    const c = mount(SectionCard, { props: { title: 'X', collapsedByDefault: true }, slots: { default: '<p class="body">hi</p>' } })
    expect(c.find('.body').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/composables src/components`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement**

`src/composables/useAudioPlayer.ts`:

```ts
import { ref } from 'vue'
import { fileUrl } from '../utils/fileUrl'

const playing = ref<string | null>(null)
let el: HTMLAudioElement | null = null

function element(): HTMLAudioElement {
  if (!el) {
    el = new Audio()
    el.addEventListener('ended', () => (playing.value = null))
  }
  return el
}

export function useAudioPlayer() {
  function stop() {
    if (el) el.pause()
    playing.value = null
  }
  function play(path: string) {
    if (playing.value === path) return stop()
    const a = element()
    a.src = fileUrl(path)
    void a.play().catch(() => (playing.value = null))
    playing.value = path
  }
  return { playing, play, stop }
}
```

`src/components/shared/ClipCompare.vue`:

```vue
<script setup lang="ts">
import { useAudioPlayer } from '../../composables/useAudioPlayer'

export interface ClipItem {
  key: string
  label: string
  path: string | null
}
defineProps<{ clips: ClipItem[] }>()
const { play, playing } = useAudioPlayer()
</script>

<template>
  <div class="compare">
    <button
      v-for="c in clips"
      :key="c.key"
      class="clip"
      :class="{ 'is-playing': c.path !== null && playing === c.path }"
      :disabled="!c.path"
      :title="c.path ? c.label : 'no clip'"
      @click="c.path && play(c.path)"
    >
      {{ c.label }}
    </button>
  </div>
</template>

<style scoped>
.compare { display: flex; gap: 6px; flex-wrap: wrap; }
.clip { padding: 4px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg); cursor: pointer; }
.clip:disabled { opacity: 0.45; cursor: default; }
.is-playing { background: var(--acc); color: #fff; border-color: var(--acc); }
</style>
```

`playing` is destructured from the composable's return value, so it is a top-level ref in `<script setup>` and the template unwraps it: compare `playing === c.path` directly. (In the test the mocked composable returns the plain string, which the template also compares directly.)

`src/components/shared/StarRating.vue`:

```vue
<script setup lang="ts">
const STARS = [1, 2, 3, 4, 5]
const props = defineProps<{ modelValue: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
const click = (n: number) => emit('update:modelValue', props.modelValue === n ? 0 : n)
</script>

<template>
  <span class="stars">
    <button v-for="n in STARS" :key="n" class="star" :class="{ on: modelValue >= n }" :aria-label="`${n} stars`" @click="click(n)">★</button>
  </span>
</template>

<style scoped>
.star { background: none; border: 0; padding: 0 1px; color: var(--dim); font-size: 16px; cursor: pointer; }
.star.on { color: #f0b400; }
</style>
```

`src/components/shared/SectionCard.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ title: string; collapsedByDefault?: boolean }>()
const open = ref(!props.collapsedByDefault)
</script>

<template>
  <section class="card">
    <div class="head" @click="open = !open">
      <h2>{{ open ? '▾' : '▸' }} {{ title }}</h2>
      <span class="actions" @click.stop><slot name="actions" /></span>
    </div>
    <div v-if="open" class="content"><slot /></div>
  </section>
</template>

<style scoped>
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; }
.head { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
h2 { font-size: 14px; margin: 0; }
.content { margin-top: 8px; }
</style>
```

`src/components/shared/EmptyState.vue`:

```vue
<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template><p class="empty">{{ message }}</p></template>

<style scoped>
.empty { color: var(--dim); font-size: 13px; padding: 8px 0; }
</style>
```

`src/components/shared/ModelStatus.vue`:

```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useModelStore } from '../../stores/model'

const model = useModelStore()
onMounted(model.start)
onUnmounted(model.stop)
</script>

<template>
  <span class="status" :title="model.reason || 'model ready'">
    <i class="dot" :class="model.state" /> model {{ model.state }}
  </span>
</template>

<style scoped>
.status { font-size: 12px; color: var(--dim); display: inline-flex; align-items: center; gap: 6px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--bad); display: inline-block; }
.dot.ready { background: var(--ok); }
.dot.busy { background: #f0b400; }
</style>
```

`src/components/shared/AppShell.vue`:

```vue
<script setup lang="ts">
import ModelStatus from './ModelStatus.vue'
</script>

<template>
  <header class="bar">
    <h1>Voice Studio</h1>
    <nav><RouterLink to="/speakers">Speakers</RouterLink></nav>
    <span class="spacer" />
    <ModelStatus />
  </header>
  <main class="main"><slot /></main>
</template>

<style>
:root { --bg: #14161a; --card: #1e2430; --line: #2c3444; --fg: #e8e8e8; --dim: #98a2b3; --ok: #3fb68b; --bad: #e5645b; --acc: #6aa5ff; }
@media (prefers-color-scheme: light) { :root { --bg: #f4f5f7; --card: #fff; --line: #d5d9e0; --fg: #1b1f27; --dim: #5b6472; --acc: #1f5fd1; } }
* { box-sizing: border-box; }
body { margin: 0; font: 14px system-ui, sans-serif; background: var(--bg); color: var(--fg); }
button, input, select, textarea { font: inherit; color: var(--fg); background: var(--card); border: 1px solid var(--line); border-radius: 6px; padding: 5px 9px; }
button { cursor: pointer; }
button:disabled { opacity: 0.5; cursor: default; }
a { color: var(--acc); }
</style>

<style scoped>
.bar { position: sticky; top: 0; z-index: 5; display: flex; gap: 14px; align-items: center; padding: 8px 16px; background: var(--bg); border-bottom: 1px solid var(--line); }
h1 { font-size: 16px; margin: 0; }
.spacer { flex: 1; }
.main { padding: 12px 16px; }
</style>
```

`src/App.vue`:

```vue
<script setup lang="ts">
import AppShell from './components/shared/AppShell.vue'
</script>

<template>
  <AppShell>
    <RouterView v-slot="{ Component, route }">
      <component :is="Component" :key="route.fullPath" />
    </RouterView>
  </AppShell>
</template>
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass; type check clean.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)

---

### Task 10: Speakers list view

**Files:**
- Modify: `src/views/SpeakersView.vue`
- Test: `src/views/SpeakersView.test.ts`

**Interfaces:**
- Consumes: `useSpeakersStore`, `EmptyState`.
- Produces: route `/speakers` rendering the speakers grouped by status (needs voice, has source, profile saved), each a `RouterLink` to `/speakers/<slug>` with name, origin chip and line count; a name filter input; empty states for "no speakers" and "no match".

- [ ] **Step 1: Write the failing test**

`src/views/SpeakersView.test.ts`:

```ts
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import SpeakersView from './SpeakersView.vue'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn() } }))

const sp = (name: string, status: string, origin = 'real') => ({ slug: name.toLowerCase(), name, origin, line_count: 3, status })
const link = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

describe('SpeakersView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('groups speakers and links to their page', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('Pasqal', 'source'), sp('Muaran', 'needs_voice', 'designed')] as never)
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w.text()).toContain('Needs a voice')
    expect(w.find('a[href="/speakers/muaran"]').exists()).toBe(true)
    expect(w.text()).toContain('designed')
  })

  it('filters by name and shows a no-match message', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('Pasqal', 'source')] as never)
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    await w.find('input').setValue('zzz')
    expect(w.text()).toContain('No speakers match')
  })

  it('shows an empty state and an error message', async () => {
    vi.mocked(api.speakers).mockResolvedValue([])
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w.text()).toContain('No speakers yet')
    vi.mocked(api.speakers).mockRejectedValue(new Error('server down'))
    const w2 = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w2.text()).toContain('server down')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/views/SpeakersView.test.ts`
Expected: FAIL (placeholder view has none of this text).

- [ ] **Step 3: Implement**

`src/views/SpeakersView.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EmptyState from '../components/shared/EmptyState.vue'
import type { SpeakerStatus } from '../api/types'
import { useSpeakersStore } from '../stores/speakers'

const store = useSpeakersStore()
const filter = ref('')
onMounted(store.load)

const GROUPS: { status: SpeakerStatus; title: string }[] = [
  { status: 'needs_voice', title: 'Needs a voice' },
  { status: 'source', title: 'Has a source' },
  { status: 'profile', title: 'Profile saved' },
]

const visible = computed(() => {
  const q = filter.value.trim().toLowerCase()
  return GROUPS.map((g) => ({
    ...g,
    items: store.byStatus[g.status].filter((s) => !q || s.name.toLowerCase().includes(q)),
  })).filter((g) => g.items.length)
})
</script>

<template>
  <div>
    <input v-model="filter" placeholder="filter speakers" />
    <p v-if="store.error" class="err">{{ store.error }}</p>
    <EmptyState v-else-if="!store.list.length && !store.loading" message="No speakers yet." />
    <EmptyState v-else-if="!visible.length" message="No speakers match the filter." />
    <section v-for="g in visible" :key="g.status">
      <h2>{{ g.title }} <span class="dim">{{ g.items.length }}</span></h2>
      <RouterLink v-for="s in g.items" :key="s.slug" class="row" :to="`/speakers/${s.slug}`">
        <b>{{ s.name }}</b>
        <span class="chip">{{ s.origin }}</span>
        <span class="dim">{{ s.line_count }} lines</span>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped>
h2 { font-size: 14px; margin: 16px 0 4px; }
.row { display: flex; gap: 10px; align-items: center; padding: 6px 8px; border-bottom: 1px solid var(--line); text-decoration: none; color: var(--fg); }
.row:hover { background: var(--card); }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); }
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)

---

### Task 11: Speaker state, context and page shell with profile bar

**Files:**
- Create: `src/composables/useSpeakerState.ts`, `src/composables/useSpeakerContext.ts`, `src/components/profile/ProfileBar.vue`
- Modify: `src/views/SpeakerView.vue`
- Tests: `src/composables/useSpeakerState.test.ts`, `src/components/profile/ProfileBar.test.ts`

**Interfaces:**
- Consumes: `api`, types, `useModelStore`, `ClipCompare`, `SectionCard`.
- Produces (`useSpeakerState(slug: string): SpeakerContext`):

```ts
export interface SpeakerContext {
  slug: string
  detail: Ref<SpeakerDetail | null>
  lines: Ref<Line[]>
  takes: Ref<Take[]>
  fxAvailable: Ref<string[]>
  options: Ref<ModelOptions>
  fxChosen: Ref<string[]>
  supplied: Ref<SourceClip[]>
  selectedSources: Ref<Set<string>>        // keys of SourceClip
  selectedLines: Ref<Set<string>>          // guids
  sources: ComputedRef<SourceClip[]>       // real clips + design candidates (ranked order) + supplied
  chosenSources: ComputedRef<SourceClip[]> // sources whose key is selected, in `sources` order
  loading: Ref<boolean>
  error: Ref<string | null>
  load(): Promise<void>                    // detail + lines + takes + fx presets; applies profile if present
  addSupplied(wav: string, text: string): void
  upsertTake(t: Take): void
  saveProfile(): Promise<void>             // source = first chosen source
  setActive(): Promise<void>
  registerPick(): Promise<void>            // designed speakers: copy the picked candidate into the prompt bank, then reload
  notice: Ref<string>                      // last success/failure text for ProfileBar
}
```
  `provideSpeakerContext(ctx)` / `useSpeakerContext()` (typed `InjectionKey`, throws outside a provider). Source keys: real `real:<id>`, candidate `cand:<id>`, supplied `sup:<wav>`.

- [ ] **Step 1: Write the failing tests**

`src/composables/useSpeakerState.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useSpeakerState } from './useSpeakerState'

vi.mock('../api/client', () => ({
  api: { speaker: vi.fn(), lines: vi.fn(), takes: vi.fn(), fxPresets: vi.fn(), saveProfile: vi.fn(), setActive: vi.fn(), register: vi.fn() },
}))

const opts = { cfg: 2, timesteps: 10, seed: '', use_instruct: false, retry_badcase: false, normalize: false, continuation: false }
const realDetail = {
  summary: { slug: 'pasqal', name: 'Pasqal', origin: 'real', line_count: 2, status: 'source' },
  clips: [{ id: 'E1', wav: 'data/v/E1.wav', duration: 5, text: 'Hello.', curated_rank: 1, noise_db: -60 }],
  design: null, profile: null,
}
const designDetail = {
  summary: { slug: 'muaran', name: 'Muaran', origin: 'designed', line_count: 1, status: 'source' },
  clips: [],
  design: { description: 'd', text: 'Sample.', order: ['c1.wav'], pick: 'c1.wav',
    candidates: [{ id: 'c1.wav', file: 'data/vd/c1.wav', scores: null, verdict: {}, gen: null }, { id: 'c0.wav', file: 'data/vd/c0.wav', scores: null, verdict: {}, gen: null }] },
  profile: null,
}

function setup(detail: unknown) {
  vi.mocked(api.speaker).mockResolvedValue(detail as never)
  vi.mocked(api.lines).mockResolvedValue([{ guid: 'g1' }] as never)
  vi.mocked(api.takes).mockResolvedValue([])
  vi.mocked(api.fxPresets).mockResolvedValue(['Clean'])
}

describe('useSpeakerState', () => {
  beforeEach(() => vi.clearAllMocks())

  it('builds sources from real clips and defaults to the first', async () => {
    setup(realDetail)
    const s = useSpeakerState('pasqal')
    await s.load()
    expect(s.sources.value.map((x) => x.key)).toEqual(['real:E1'])
    expect(s.chosenSources.value.map((x) => x.key)).toEqual(['real:E1'])
    expect(s.lines.value).toHaveLength(1)
    expect(s.fxAvailable.value).toEqual(['Clean'])
  })

  it('uses design candidates as sources with the design sample text, ranked order first', async () => {
    setup(designDetail)
    const s = useSpeakerState('muaran')
    await s.load()
    expect(s.sources.value.map((x) => [x.key, x.text])).toEqual([['cand:c1.wav', 'Sample.'], ['cand:c0.wav', 'Sample.']])
    expect(s.chosenSources.value.map((x) => x.key)).toEqual(['cand:c1.wav'])    // the pick is preselected
  })

  it('has no sources and no selection for an empty speaker', async () => {
    setup({ ...realDetail, clips: [] })
    const s = useSpeakerState('pasqal')
    await s.load()
    expect(s.sources.value).toEqual([])
    expect(s.chosenSources.value).toEqual([])
  })

  it('applies a saved profile to options, fx, lines and the chosen source', async () => {
    setup({ ...realDetail, profile: { source: { wav: 'data/v/E1.wav', text: 'Hello.', origin: 'real' }, options: { ...opts, cfg: 3.5 }, fx: ['Clean'], test_lines: ['g1'] } })
    const s = useSpeakerState('pasqal')
    await s.load()
    expect(s.options.value.cfg).toBe(3.5)
    expect(s.fxChosen.value).toEqual(['Clean'])
    expect([...s.selectedLines.value]).toEqual(['g1'])
    expect(s.chosenSources.value.map((x) => x.wav)).toEqual(['data/v/E1.wav'])
  })

  it('supplied clips are added as selectable sources, deduplicated', async () => {
    setup({ ...realDetail, clips: [] })
    const s = useSpeakerState('pasqal')
    await s.load()
    s.addSupplied('data/x/clean.wav', 'text')
    s.addSupplied('data/x/clean.wav', 'text')
    expect(s.sources.value.map((x) => x.key)).toEqual(['sup:data/x/clean.wav'])
  })

  it('saveProfile uses the first chosen source and reports success; refuses with none chosen', async () => {
    setup(realDetail)
    vi.mocked(api.saveProfile).mockResolvedValue({} as never)
    const s = useSpeakerState('pasqal')
    await s.load()
    await s.saveProfile()
    expect(vi.mocked(api.saveProfile).mock.calls[0][1]).toMatchObject({ source: { wav: 'data/v/E1.wav', origin: 'real' } })
    expect(s.notice.value).toMatch(/saved/i)
    s.selectedSources.value = new Set()
    await s.saveProfile()
    expect(s.notice.value).toMatch(/choose a source/i)
  })

  it('upsertTake puts new takes first and replaces existing ones', async () => {
    setup(realDetail)
    const s = useSpeakerState('pasqal')
    await s.load()
    s.upsertTake({ id: 't1', rating: 0 } as never)
    s.upsertTake({ id: 't2', rating: 0 } as never)
    s.upsertTake({ id: 't1', rating: 5 } as never)
    expect(s.takes.value.map((t) => [t.id, t.rating])).toEqual([['t2', 0], ['t1', 5]])
  })

  it('registerPick calls the api, reloads, and reports errors in the notice', async () => {
    setup(designDetail)
    vi.mocked(api.register).mockResolvedValue({ registered: ['Muaran'] })
    const s = useSpeakerState('muaran')
    await s.load()
    await s.registerPick()
    expect(api.register).toHaveBeenCalledWith('muaran')
    expect(s.notice.value).toContain('Registered Muaran')
    expect(api.speaker).toHaveBeenCalledTimes(2)
    vi.mocked(api.register).mockRejectedValue(new Error("'Muaran' has no pick yet"))
    await s.registerPick()
    expect(s.notice.value).toContain('no pick yet')
  })

  it('records load errors', async () => {
    vi.mocked(api.speaker).mockRejectedValue(new Error('no speaker'))
    const s = useSpeakerState('x')
    await s.load()
    expect(s.error.value).toBe('no speaker')
  })
})
```

`src/components/profile/ProfileBar.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ProfileBar from './ProfileBar.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

describe('ProfileBar', () => {
  it('calls saveProfile and setActive and shows the notice', async () => {
    const ctx = { saveProfile: vi.fn(), setActive: vi.fn(), notice: ref('saved'), detail: ref({ profile: { saved: 'today' } }) }
    const w = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    const [save, active] = w.findAll('button')
    await save.trigger('click')
    await active.trigger('click')
    expect(ctx.saveProfile).toHaveBeenCalled()
    expect(ctx.setActive).toHaveBeenCalled()
    expect(w.text()).toContain('saved')
  })

  it('shows Register pick only for designed speakers and disables it without a pick', async () => {
    const mk = (design: unknown) => ({ saveProfile: vi.fn(), setActive: vi.fn(), registerPick: vi.fn(), notice: ref(''), detail: ref({ profile: null, design }) })
    const none = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: mk(null) } } })
    expect(none.find('[data-register]').exists()).toBe(false)
    const noPick = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: mk({ pick: null }) } } })
    expect(noPick.find('[data-register]').attributes('disabled')).toBeDefined()
    const ctx = mk({ pick: 'c1.wav' })
    const w = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.find('[data-register]').trigger('click')
    expect(ctx.registerPick).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run src/composables/useSpeakerState.test.ts src/components/profile`
Expected: FAIL, modules not found.

- [ ] **Step 3: Implement**

`src/composables/useSpeakerContext.ts`:

```ts
import { inject, provide, type InjectionKey } from 'vue'
import type { SpeakerContext } from './useSpeakerState'

export const SPEAKER_CTX_KEY: InjectionKey<SpeakerContext> = Symbol('speakerContext')

export const provideSpeakerContext = (ctx: SpeakerContext) => provide(SPEAKER_CTX_KEY, ctx)

export function useSpeakerContext(): SpeakerContext {
  const ctx = inject(SPEAKER_CTX_KEY)
  if (!ctx) throw new Error('useSpeakerContext must be used inside a speaker page')
  return ctx
}
```

`src/composables/useSpeakerState.ts`:

```ts
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

  return { slug, detail, lines, takes, fxAvailable, options, fxChosen, supplied, selectedSources, selectedLines, sources, chosenSources, loading, error, notice, load, addSupplied, upsertTake, saveProfile, setActive, registerPick }
}
```

`src/components/profile/ProfileBar.vue`:

```vue
<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'

const ctx = useSpeakerContext()
</script>

<template>
  <div class="bar">
    <button @click="ctx.saveProfile()">Save profile</button>
    <button @click="ctx.setActive()" :disabled="!ctx.detail.value?.profile" title="Copy the saved profile to active.json">Set active</button>
    <button
      v-if="ctx.detail.value?.design"
      data-register
      :disabled="!ctx.detail.value.design.pick"
      title="Copy the rank-1 candidate into the prompt bank so plan.py can use it"
      @click="ctx.registerPick()"
    >Register pick</button>
    <span class="dim">{{ ctx.detail.value?.profile ? `saved ${ctx.detail.value.profile.saved}` : 'no profile saved yet' }}</span>
    <span class="notice">{{ ctx.notice.value }}</span>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.dim { color: var(--dim); font-size: 12px; }
.notice { color: var(--ok); font-size: 13px; }
</style>
```

(In the `ProfileBar` test the context holds plain refs, so templates call `ctx.notice.value`. If the template reads `ctx.notice` it would show the ref object; keep `.value` as written.)

`src/views/SpeakerView.vue` (sections are added in Tasks 12 to 14; this version renders the header and profile bar and a loading/error state):

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import EmptyState from '../components/shared/EmptyState.vue'
import ProfileBar from '../components/profile/ProfileBar.vue'
import { provideSpeakerContext } from '../composables/useSpeakerContext'
import { useSpeakerState } from '../composables/useSpeakerState'

const props = defineProps<{ slug: string }>()
const ctx = useSpeakerState(props.slug)
provideSpeakerContext(ctx)
onMounted(ctx.load)
</script>

<template>
  <div>
    <p v-if="ctx.error.value" class="err">{{ ctx.error.value }}</p>
    <EmptyState v-else-if="!ctx.detail.value" message="Loading…" />
    <template v-else>
      <h1>{{ ctx.detail.value.summary.name }} <span class="dim">{{ ctx.detail.value.summary.origin }} voice</span></h1>
      <ProfileBar />
      <!-- sections are added in Tasks 12 to 14 -->
    </template>
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.dim { color: var(--dim); font-size: 13px; }
.err { color: var(--bad); }
</style>
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all pass; type check clean.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)
