# Voice Studio first slice, part 3 of 7: Web foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Overview and table of contents:** [Voice Studio first slice](../2026-10-09-voice-studio-first-slice.md). Read it first: it holds the goal, architecture, file structure and review focus for the whole slice.
**Spec:** [`docs/superpowers/specs/2026-10-09-voice-studio-design.md`](../../specs/2026-10-09-voice-studio-design.md)
**This part:** Tasks 7 to 8. Vue app: scaffold, typed API client, utilities and stores.
**Previous part:** [Server live calls and HTTP app](02-server-live-and-api.md). **Next part:** [Web shell, speakers list, speaker state](04-web-shell-and-speakers.md).

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

### Task 7: Web scaffold, API types and client

**Files:**
- Create: `tools/studio/web/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.ts`, `src/App.vue`, `src/router.ts`, `src/api/types.ts`, `src/api/client.ts`, `src/views/SpeakersView.vue` (placeholder replaced in Task 10), `src/views/SpeakerView.vue` (placeholder replaced in Task 11), `src/api/client.test.ts`
- Modify: `.gitignore` (add `tools/studio/web/node_modules/` and `tools/studio/web/dist/`)

**Interfaces:**
- Produces: all API types (below) and `api` client object with one method per route, each returning typed JSON and throwing `ApiRequestError(status, message)` on a non-2xx response.

- [ ] **Step 1: Scaffold files**

`package.json`:

```json
{
  "name": "voice-studio-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc --noEmit && vite build",
    "test": "vitest run",
    "typecheck": "vue-tsc --noEmit"
  },
  "dependencies": {
    "pinia": "^2.2.0",
    "vue": "^3.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.1.0",
    "@vue/test-utils": "^2.4.6",
    "happy-dom": "^15.0.0",
    "typescript": "~5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0",
    "vue-tsc": "^2.1.0"
  }
}
```

`vite.config.ts`:

```ts
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

const API_PORT = 8930

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${API_PORT}`,
      '/file': `http://127.0.0.1:${API_PORT}`,
    },
  },
  test: { environment: 'happy-dom', globals: true },
})
```

`tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "types": ["vitest/globals"],
    "skipLibCheck": true,
    "noEmit": true,
    "isolatedModules": true
  },
  "include": ["src/**/*.ts", "src/**/*.vue", "vite.config.ts"]
}
```

`index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Voice Studio</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

`src/main.ts`:

```ts
import { createPinia } from 'pinia'
import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
```

`src/router.ts`:

```ts
import { createRouter, createWebHistory } from 'vue-router'
import SpeakersView from './views/SpeakersView.vue'
import SpeakerView from './views/SpeakerView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/speakers' },
    { path: '/speakers', component: SpeakersView },
    { path: '/speakers/:slug', component: SpeakerView, props: true },
  ],
})
```

`src/App.vue` (replaced by `AppShell` usage in Task 9):

```vue
<script setup lang="ts"></script>

<template>
  <RouterView />
</template>
```

Placeholder views (`SpeakersView.vue`, `SpeakerView.vue`): each is `<template><p>todo view</p></template>` with an empty `<script setup lang="ts"></script>`. They are replaced in Tasks 10 and 11.

- [ ] **Step 2: Write the failing test for the client**

`src/api/client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, api } from './client'

function mockFetch(status: number, body: unknown) {
  const f = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body })
  vi.stubGlobal('fetch', f)
  return f
}

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('GETs JSON', async () => {
    const f = mockFetch(200, [{ slug: 'pasqal' }])
    expect(await api.speakers()).toEqual([{ slug: 'pasqal' }])
    expect(f).toHaveBeenCalledWith('/api/speakers', undefined)
  })

  it('POSTs JSON bodies', async () => {
    const f = mockFetch(200, { cand: 'c2.wav' })
    await api.designKeep('muaran', { file: 'live_tmp/t.wav', seed: 1, cfg: 2, timesteps: 10 })
    const [url, init] = f.mock.calls[0]
    expect(url).toBe('/api/speakers/muaran/design/keep')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toMatchObject({ seed: 1 })
  })

  it('throws ApiRequestError with the server message', async () => {
    mockFetch(503, { error: 'model backend is not running' })
    await expect(api.designGenerate('muaran', {})).rejects.toMatchObject({
      status: 503,
      message: 'model backend is not running',
    })
    await expect(api.designGenerate('muaran', {})).rejects.toBeInstanceOf(ApiRequestError)
  })
})
```

- [ ] **Step 3: Install and verify failure**

Run: `cd tools/studio/web && npm install && npx vitest run src/api/client.test.ts`
Expected: FAIL, `Failed to resolve import "./client"`.

- [ ] **Step 4: Implement types and client**

`src/api/types.ts`:

```ts
export type Origin = 'real' | 'designed' | 'supplied'
export type SpeakerStatus = 'needs_voice' | 'source' | 'profile'
export type ModelState = 'down' | 'ready' | 'busy'

export interface SpeakerSummary {
  slug: string
  name: string
  origin: 'real' | 'designed'
  line_count: number
  status: SpeakerStatus
}

export interface RealClip {
  id: string
  wav: string
  duration: number
  text: string
  curated_rank: number | null
  noise_db: number | null
}

export interface Verdict {
  accent?: 'british' | 'american' | 'other'
  fit?: number
  reject?: boolean
}

export interface Candidate {
  id: string
  file: string
  scores: { p_us: number; top: string; p_top: number } | null
  verdict: Verdict
  gen: { seed?: number; cfg?: number; timesteps?: number; live?: boolean } | null
}

export interface DesignState {
  description: string
  text: string
  candidates: Candidate[]
  order: string[]
  pick: string | null
}

export interface ModelOptions {
  cfg: number
  timesteps: number
  seed: string
  use_instruct: boolean
  retry_badcase: boolean
  normalize: boolean
  continuation: boolean
}

export interface SourceRef {
  wav: string
  text: string
  origin: Origin
}

export interface VoiceProfile {
  name: string
  slug: string
  kind: 'speaker'
  source: SourceRef
  options: ModelOptions
  fx: string[]
  test_lines: string[]
  notes: string
  saved: string
}

export interface SpeakerDetail {
  summary: SpeakerSummary
  clips: RealClip[]
  design: DesignState | null
  profile: VoiceProfile | null
}

export interface Line {
  guid: string
  text: string
  emotion: string | null
  intensity: number | null
  pace: string | null
  instruct: string | null
  baseline: string | null
}

export interface TakeFx {
  presets: string[]
  wav: string
  v: number
}

export interface Take {
  id: string
  raw: string
  text: string
  guid: string | null
  reference: string
  options: ModelOptions
  instruct: string | null
  seed: number
  seconds: number
  audio_s: number | null
  rating: number
  note: string
  fx: TakeFx | null
}

export interface LiveTake {
  file: string
  seed: number
  cfg: number
  timesteps: number
  seconds: number
  audio_s?: number
  description: string
  text: string
}

export interface CloneRequest {
  guid: string | null
  text: string
  instruct: string | null
  reference: { wav: string; text: string }
  options: ModelOptions
}

/** Anything the user can clone from: a real clip, a design candidate, or a supplied wav. */
export interface SourceClip {
  key: string
  label: string
  wav: string
  text: string
  origin: Origin
}
```

`src/api/client.ts`:

```ts
import type {
  CloneRequest, LiveTake, Line, ModelState, SpeakerDetail, SpeakerSummary, Take, Verdict, VoiceProfile,
} from './types'

export class ApiRequestError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiRequestError(res.status, (body as { error?: string }).error ?? `HTTP ${res.status}`)
  return body as T
}

const post = <T>(url: string, body: unknown = {}) =>
  request<T>(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

const S = (slug: string) => `/api/speakers/${encodeURIComponent(slug)}`

export const api = {
  health: () => request<{ state: ModelState }>('/api/model/health'),
  speakers: () => request<SpeakerSummary[]>('/api/speakers'),
  speaker: (slug: string) => request<SpeakerDetail>(S(slug)),
  lines: (slug: string) => request<Line[]>(`${S(slug)}/lines`),
  takes: (slug: string) => request<Take[]>(`${S(slug)}/takes`),
  fxPresets: () => request<string[]>('/api/fx/presets'),
  saveProfile: (slug: string, body: Partial<VoiceProfile>) => post<VoiceProfile>(`${S(slug)}/profile`, body),
  setActive: (slug: string) => post<{ active: string }>(`${S(slug)}/active`),
  designGenerate: (slug: string, body: { description?: string; seed?: string; cfg?: number; timesteps?: number }) =>
    post<LiveTake>(`${S(slug)}/design/generate`, body),
  designKeep: (slug: string, body: Partial<LiveTake>) => post<{ cand: string }>(`${S(slug)}/design/keep`, body),
  designVerdict: (slug: string, body: { cand: string; pick?: boolean } & Verdict) => post<object>(`${S(slug)}/design/verdict`, body),
  designOrder: (slug: string, order: string[]) => post<object>(`${S(slug)}/design/order`, { order }),
  designDescription: (slug: string, description: string) => post<object>(`${S(slug)}/design/description`, { description }),
  register: (slug: string) => post<{ registered: string[] }>(`${S(slug)}/register`),
  cloneGenerate: (slug: string, body: CloneRequest) => post<Take>(`${S(slug)}/clone/generate`, body),
  takeFx: (slug: string, id: string, presets: string[]) => post<Take>(`${S(slug)}/takes/${id}/fx`, { presets }),
  takeRate: (slug: string, id: string, body: { rating?: number; note?: string }) => post<Take>(`${S(slug)}/takes/${id}/rate`, body),
}
```

- [ ] **Step 5: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run src/api/client.test.ts && npx vue-tsc --noEmit`
Expected: 3 tests pass; type check clean.

- [ ] **Step 6: Checkpoint** (`git status`; `.gitignore` updated; no commit unless asked)

---

### Task 8: Utilities and stores (order, seed, file URLs, batch runner, model status, speakers)

**Files:**
- Create: `src/utils/order.ts`, `src/utils/seed.ts`, `src/utils/fileUrl.ts`, `src/utils/batch.ts`, `src/stores/model.ts`, `src/stores/speakers.ts`, with tests `src/utils/order.test.ts`, `seed.test.ts`, `fileUrl.test.ts`, `batch.test.ts`, `src/stores/model.test.ts`, `src/stores/speakers.test.ts`

**Interfaces:**
- Consumes: `api`, types (Task 7).
- Produces:
  - `moveItem<T>(list: readonly T[], from: number, to: number): T[]` (pure; out-of-range indices clamp; returns a new array)
  - `pickSeed(input: string, rand?: () => number): string` (returns `input.trim()` if non-empty else a random non-negative 31-bit integer as a string)
  - `fileUrl(path: string): string` (`'/file?p=' + encodeURIComponent(path)`; a trailing `?v=N` on the path becomes `&v=N`)
  - `runBatch(args: BatchArgs): Promise<BatchResult>` where `BatchArgs = { lines: Line[]; sources: SourceClip[]; options: ModelOptions; generate: (req: CloneRequest) => Promise<Take>; onTake: (t: Take) => void; shouldStop?: () => boolean }` and `BatchResult = { done: number; total: number; error: string | null }`. The seed is chosen once per line (via `pickSeed`) and shared by every source.
  - `useModelStore()` Pinia store: `state: ModelState` (ref), `ready` (computed), `reason` (computed, text for disabled controls), `refresh()`, `start()` and `stop()` (polling every `MODEL_POLL_MS = 5000`).
  - `useSpeakersStore()`: `list` (ref), `loading`, `error`, `load()`, `byStatus` (computed groups).

- [ ] **Step 1: Write the failing tests**

`src/utils/order.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { moveItem } from './order'

describe('moveItem', () => {
  it('moves forward and back without mutating', () => {
    const a = ['a', 'b', 'c', 'd']
    expect(moveItem(a, 0, 2)).toEqual(['b', 'c', 'a', 'd'])
    expect(moveItem(a, 3, 0)).toEqual(['d', 'a', 'b', 'c'])
    expect(a).toEqual(['a', 'b', 'c', 'd'])
  })
  it('clamps out-of-range targets and ignores bad sources', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 99)).toEqual(['b', 'c', 'a'])
    expect(moveItem(['a', 'b', 'c'], 2, -5)).toEqual(['c', 'a', 'b'])
    expect(moveItem(['a', 'b'], 5, 0)).toEqual(['a', 'b'])
    expect(moveItem([], 0, 0)).toEqual([])
  })
})
```

`src/utils/seed.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { pickSeed } from './seed'

describe('pickSeed', () => {
  it('keeps a typed seed', () => expect(pickSeed(' 4242 ')).toBe('4242'))
  it('rolls a random 31-bit integer when blank', () => {
    expect(pickSeed('', () => 0.5)).toBe(String(Math.floor(0.5 * 2 ** 31)))
    const s = Number(pickSeed('   '))
    expect(Number.isInteger(s) && s >= 0 && s < 2 ** 31).toBe(true)
  })
})
```

`src/utils/fileUrl.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { fileUrl } from './fileUrl'

describe('fileUrl', () => {
  it('encodes the path', () => expect(fileUrl('data/a b/x.wav')).toBe('/file?p=data%2Fa%20b%2Fx.wav'))
  it('turns a ?v= cache buster into a query param', () =>
    expect(fileUrl('data/studio/p/fx/t1.wav?v=77')).toBe('/file?p=data%2Fstudio%2Fp%2Ffx%2Ft1.wav&v=77'))
})
```

`src/utils/batch.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest'
import type { Line, ModelOptions, SourceClip, Take } from '../api/types'
import { runBatch } from './batch'

const OPTS: ModelOptions = { cfg: 2, timesteps: 10, seed: '', use_instruct: false, retry_badcase: false, normalize: false, continuation: false }
const line = (guid: string): Line => ({ guid, text: `text ${guid}`, emotion: null, intensity: null, pace: null, instruct: null, baseline: null })
const src = (key: string): SourceClip => ({ key, label: key, wav: `data/${key}.wav`, text: key, origin: 'real' })
const take = (n: number): Take => ({ id: `t${n}` } as Take)

describe('runBatch', () => {
  it('shares one seed per line across sources and calls every combination', async () => {
    const seen: [string, string, string][] = []
    const generate = vi.fn(async (r) => { seen.push([r.guid, r.reference.wav, r.options.seed]); return take(seen.length) })
    const onTake = vi.fn()
    const res = await runBatch({ lines: [line('a'), line('b')], sources: [src('x'), src('y')], options: OPTS, generate, onTake })
    expect(res).toEqual({ done: 4, total: 4, error: null })
    expect(onTake).toHaveBeenCalledTimes(4)
    const seeds = (g: string) => new Set(seen.filter((s) => s[0] === g).map((s) => s[2]))
    expect(seeds('a').size).toBe(1)
    expect(seeds('b').size).toBe(1)
  })

  it('keeps a typed seed for every line', async () => {
    const generate = vi.fn(async () => take(1))
    await runBatch({ lines: [line('a'), line('b')], sources: [src('x')], options: { ...OPTS, seed: '7' }, generate, onTake: vi.fn() })
    expect(generate.mock.calls.every((c) => c[0].options.seed === '7')).toBe(true)
  })

  it('stops at the first error, reports it, and keeps earlier takes', async () => {
    let n = 0
    const generate = vi.fn(async () => { if (++n === 3) throw new Error('model backend is not running'); return take(n) })
    const onTake = vi.fn()
    const res = await runBatch({ lines: [line('a'), line('b')], sources: [src('x'), src('y')], options: OPTS, generate, onTake })
    expect(res).toEqual({ done: 2, total: 4, error: 'model backend is not running' })
    expect(onTake).toHaveBeenCalledTimes(2)
  })

  it('honours shouldStop between takes', async () => {
    let stop = false
    const generate = vi.fn(async () => { stop = true; return take(1) })
    const res = await runBatch({ lines: [line('a'), line('b')], sources: [src('x')], options: OPTS, generate, onTake: vi.fn(), shouldStop: () => stop })
    expect(res.done).toBe(1)
  })

  it('waits for an async onTake before moving on or reporting done', async () => {
    const log: string[] = []
    const generate = vi.fn(async () => take(1))
    const onTake = vi.fn(async () => { await Promise.resolve(); log.push('onTake finished') })
    await runBatch({ lines: [line('a')], sources: [src('x')], options: OPTS, generate, onTake })
    log.push('batch returned')
    expect(log).toEqual(['onTake finished', 'batch returned'])
  })

  it('does nothing for empty input', async () => {
    expect(await runBatch({ lines: [], sources: [src('x')], options: OPTS, generate: vi.fn(), onTake: vi.fn() })).toEqual({ done: 0, total: 0, error: null })
  })
})
```

`src/stores/model.test.ts`:

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useModelStore } from './model'

vi.mock('../api/client', () => ({ api: { health: vi.fn() } }))

describe('model store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('is ready only in the ready state and explains why not', async () => {
    const m = useModelStore()
    vi.mocked(api.health).mockResolvedValue({ state: 'ready' })
    await m.refresh()
    expect(m.ready).toBe(true)
    vi.mocked(api.health).mockResolvedValue({ state: 'busy' })
    await m.refresh()
    expect(m.ready).toBe(false)
    expect(m.reason).toMatch(/busy/i)
  })

  it('treats a failed health call as down', async () => {
    const m = useModelStore()
    vi.mocked(api.health).mockRejectedValue(new Error('net'))
    await m.refresh()
    expect(m.state).toBe('down')
    expect(m.reason).toMatch(/live_backend/)
  })
})
```

`src/stores/speakers.test.ts`:

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useSpeakersStore } from './speakers'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn() } }))

const sp = (name: string, status: string) => ({ slug: name.toLowerCase(), name, origin: 'real', line_count: 1, status })

describe('speakers store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads and groups by status', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('A', 'needs_voice'), sp('B', 'profile'), sp('C', 'needs_voice')] as never)
    const s = useSpeakersStore()
    await s.load()
    expect(s.byStatus.needs_voice.map((x) => x.name)).toEqual(['A', 'C'])
    expect(s.byStatus.profile).toHaveLength(1)
    expect(s.byStatus.source).toEqual([])
  })

  it('records an error and keeps the list empty', async () => {
    vi.mocked(api.speakers).mockRejectedValue(new Error('down'))
    const s = useSpeakersStore()
    await s.load()
    expect(s.error).toBe('down')
    expect(s.list).toEqual([])
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd tools/studio/web && npx vitest run`
Expected: FAIL, imports for `./order`, `./seed`, `./fileUrl`, `./batch`, `./model`, `./speakers` unresolved.

- [ ] **Step 3: Implement**

`src/utils/order.ts`:

```ts
export function moveItem<T>(list: readonly T[], from: number, to: number): T[] {
  const out = [...list]
  if (from < 0 || from >= out.length) return out
  const [item] = out.splice(from, 1)
  out.splice(Math.max(0, Math.min(to, out.length)), 0, item)
  return out
}
```

`src/utils/seed.ts`:

```ts
const SEED_RANGE = 2 ** 31

export function pickSeed(input: string, rand: () => number = Math.random): string {
  const typed = input.trim()
  return typed || String(Math.floor(rand() * SEED_RANGE))
}
```

`src/utils/fileUrl.ts`:

```ts
export function fileUrl(path: string): string {
  const [p, v] = path.split('?')
  return `/file?p=${encodeURIComponent(p)}${v ? `&${v}` : ''}`
}
```

`src/utils/batch.ts`:

```ts
import type { CloneRequest, Line, ModelOptions, SourceClip, Take } from '../api/types'
import { pickSeed } from './seed'

export interface BatchArgs {
  lines: Line[]
  sources: SourceClip[]
  options: ModelOptions
  generate: (req: CloneRequest) => Promise<Take>
  onTake: (t: Take) => void | Promise<void>
  shouldStop?: () => boolean
}

export interface BatchResult {
  done: number
  total: number
  error: string | null
}

/** Every line x every source. One seed per line is shared by all sources so differences come from the source clip. */
export async function runBatch(a: BatchArgs): Promise<BatchResult> {
  const total = a.lines.length * a.sources.length
  let done = 0
  for (const line of a.lines) {
    const seed = pickSeed(a.options.seed)
    for (const src of a.sources) {
      if (a.shouldStop?.()) return { done, total, error: null }
      try {
        const take = await a.generate({
          guid: line.guid,
          text: line.text,
          instruct: line.instruct,
          reference: { wav: src.wav, text: src.text },
          options: { ...a.options, seed },
        })
        await a.onTake(take)
        done++
      } catch (e) {
        return { done, total, error: e instanceof Error ? e.message : String(e) }
      }
    }
  }
  return { done, total, error: null }
}
```

`src/stores/model.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { ModelState } from '../api/types'

const MODEL_POLL_MS = 5000
const REASONS: Record<ModelState, string> = {
  ready: '',
  busy: 'The model is busy with another request.',
  down: 'The model backend is not running (start tools/voice_design/live_backend.py when the GPU is free).',
}

export const useModelStore = defineStore('model', () => {
  const state = ref<ModelState>('down')
  const ready = computed(() => state.value === 'ready')
  const reason = computed(() => REASONS[state.value])
  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    try {
      state.value = (await api.health()).state
    } catch {
      state.value = 'down'
    }
  }
  function start() {
    if (timer) return
    refresh()
    timer = setInterval(refresh, MODEL_POLL_MS)
  }
  function stop() {
    if (timer) clearInterval(timer)
    timer = null
  }
  return { state, ready, reason, refresh, start, stop }
})
```

`src/stores/speakers.ts`:

```ts
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { SpeakerStatus, SpeakerSummary } from '../api/types'

export const useSpeakersStore = defineStore('speakers', () => {
  const list = ref<SpeakerSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const byStatus = computed(() => {
    const g: Record<SpeakerStatus, SpeakerSummary[]> = { needs_voice: [], source: [], profile: [] }
    for (const s of list.value) g[s.status].push(s)
    return g
  })

  async function load() {
    loading.value = true
    error.value = null
    try {
      list.value = await api.speakers()
    } catch (e) {
      list.value = []
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }
  return { list, loading, error, byStatus, load }
})
```

- [ ] **Step 4: Run to verify pass**

Run: `cd tools/studio/web && npx vitest run && npx vue-tsc --noEmit`
Expected: all tests pass; type check clean.

- [ ] **Step 5: Checkpoint** (`git status`; no commit unless asked)
