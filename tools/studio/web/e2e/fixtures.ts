import { expect, test as base, type Locator, type Page } from '@playwright/test'

export interface Monitor { corr: number | null; sideMidDb: number | null; balanceDb: number | null; bands: (number | null)[]; samples: number }
export interface QaGraph {
  name: string
  nodes: Array<{ id: string; type: string; on?: boolean }>
  edges: Array<{ id: string; source: string; target: string; targetPort: number }>
}
interface QaControl { key: string; nodeId: string; label: string }

/** The page's `window.__pedalboard` (src/qa/pedalboardQaHook.ts), called from the test process. */
export class Qa {
  constructor(private readonly page: Page) {}
  private call<T>(method: string, ...args: unknown[]): Promise<T> {
    return this.page.evaluate(({ m, a }) => (window as any).__pedalboard[m](...a), { m: method, a: args }) as Promise<T>
  }
  graph = () => this.call<QaGraph>('graph')
  compiled = () => this.call<{ code: string; controls: QaControl[] } | null>('compiled')
  engineStatus = () => this.call<{ status: string; error: string }>('engineStatus')
  compileCount = () => this.call<number>('compileCount')
  paramValue = (key: string) => this.call<number | undefined>('paramValue', key)
  monitor = () => this.call<Monitor>('monitor')
  selection = () => this.call<string[]>('selection')
  loadSyntheticClip = (seconds: number) => this.call<void>('loadSyntheticClip', seconds)
  loadStarterBySlug = (slug: string) => this.call<boolean>('loadStarterBySlug', slug)
  /** The flat key of a pedal's stomp checkbox, read from the compiled controls (it ends in `_on`). */
  async stompKey(nodeId: string): Promise<string> {
    const c = await this.compiled()
    const hit = c?.controls.find((x) => x.nodeId === nodeId && /_on$/.test(x.key))
    if (!hit) throw new Error(`no stomp control for ${nodeId}`)
    return hit.key
  }
  /** Wait for the debounced compile to land and the engine to settle, then confirm nothing else is queued. */
  async settled(): Promise<number> {
    await expect.poll(async () => (await this.engineStatus()).status, { timeout: 30_000 }).toBe('ready')
    await this.page.waitForTimeout(700)           // longer than the 300 ms debounce, so a late second compile would show
    await expect.poll(async () => (await this.engineStatus()).status).toBe('ready')
    return this.compileCount()
  }
}

/** 404s from /api/ on the fake root: pages ask for data the mock stack does not have (pools, matches, casting). Never 5xx. */
export const FAKE_ROOT_404 = /\/api\/(pools|matches|casting|assignments)/

/** Collects console errors, page errors, failed requests and HTTP errors; `allow404` lists URLs whose 404 is expected. Favicon is ignored. */
export function watchProblems(page: Page, allow404?: RegExp): string[] {
  const problems: string[] = []
  const expected = (url: string, status: number) => status === 404 && !!allow404 && allow404.test(url)
  page.on('console', (m) => {
    // The browser logs a generic line for every failed fetch; the response handler below names the URL, so only that one is judged.
    if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) problems.push(`console: ${m.text()}`)
  })
  page.on('pageerror', (e) => problems.push(`pageerror: ${e.message}`))
  page.on('requestfailed', (r) => { if (!/favicon/.test(r.url())) problems.push(`request failed: ${r.url()}`) })
  page.on('response', (r) => {
    if (r.status() >= 400 && !/favicon/.test(r.url()) && !expected(r.url(), r.status())) problems.push(`HTTP ${r.status()}: ${r.url()}`)
  })
  return problems
}

export interface Board {
  page: Page
  qa: Qa
  /** Console errors, page errors and failed requests seen so far (favicon ignored). */
  problems: string[]
  canvas: Locator
}

export const test = base.extend<{ board: Board }>({
  baseURL: async ({}, use) => use(process.env.E2E_BASE_URL),
  board: async ({ page }, use) => {
    const problems = watchProblems(page, FAKE_ROOT_404)
    await page.goto('/pedalboard?qa')
    await expect(page.getByTestId('palette')).toBeVisible()
    await page.waitForFunction(() => !!(window as any).__pedalboard)
    await use({ page, qa: new Qa(page), problems, canvas: page.getByTestId('canvas') })
  },
})
export { expect }

export const STARTER = 'rt-tech-priest-pasqal-target-stereo'

export async function loadStarter(board: Board, slug: string): Promise<void> {
  await board.page.getByTestId('preset-starters').click()
  await board.page.getByTestId(`starter-${slug}`).click()
}

/** Drag a wire from one pedal's output handle to another's input handle with real mouse events. */
export async function wire(page: Page, from: string, to: string, port = 0): Promise<void> {
  const a = await page.getByTestId(`out-${from}`).boundingBox()
  const b = await page.getByTestId(`in-${to}-${port}`).boundingBox()
  if (!a || !b) throw new Error(`handle not visible for ${from} -> ${to}`)
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
  await page.mouse.down()
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 8 })
  await page.mouse.up()
}

export async function addPedal(board: Board, blockId: string): Promise<void> {
  await board.page.getByTestId(`palette-${blockId}`).dblclick()
}
