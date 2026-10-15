import { expect, loadStarter, STARTER, test, addPedal, wire } from './fixtures'

const DEBOUNCE_MARGIN_MS = 700
const MIN_ZOOM = 0.4
const MIN_FIT_ZOOM_SETTLE_MS = 10_000

test.describe('pedalboard page', () => {
  test('loads with no console errors or failed requests', async ({ board }) => {
    await board.page.waitForTimeout(800)
    expect(board.problems).toEqual([])
  })

  test('palette shows 31 pedals in 7 categories', async ({ board }) => {
    const groups = board.page.locator('[data-testid^="palette-group-"]')
    await expect(groups).toHaveCount(7)
    await expect(board.page.locator('.palette .item')).toHaveCount(31)
  })

  test('starter lays out 14 nodes, 13 drawn wires, no overlap, nothing off-canvas, readable zoom', async ({ board }) => {
    await loadStarter(board, STARTER)
    await expect(board.page.locator('.vue-flow__node')).toHaveCount(14)
    // The wires are the regression: Vue Flow once rejected every existing edge, so none were drawn.
    await expect(board.page.locator('.vue-flow__edge')).toHaveCount(13)
    const pane = board.page.locator('.vue-flow__transformationpane')
    const transform = () => pane.evaluate((el) => getComputedStyle(el).transform)
    // The fit-to-view runs a moment after the load (Vue Flow measures the nodes first): wait until the view has moved off its initial
    // identity transform and then stopped moving, so zoom and positions are measured after it, not before.
    let last = ''
    await expect.poll(async () => {
      const now = await transform()
      const settled = now === last && now !== 'matrix(1, 0, 0, 1, 0, 0)' && now !== 'none'
      last = now
      return settled
    }, { timeout: MIN_FIT_ZOOM_SETTLE_MS, intervals: [400] }).toBe(true)
    const zoom = Number(/matrix\(([-\d.e]+),/.exec(await transform())?.[1])
    expect(zoom, 'zoom after fit-view').toBeGreaterThanOrEqual(MIN_ZOOM)
    const canvas = await board.canvas.boundingBox()
    const boxes = await board.page.locator('.vue-flow__node').evaluateAll((els) =>
      els.map((e) => { const r = e.getBoundingClientRect(); return { id: e.getAttribute('data-id'), x: r.x, y: r.y, w: r.width, h: r.height } }))
    expect(boxes).toHaveLength(14)
    for (const b of boxes) {
      expect(b.x, `${b.id} left`).toBeGreaterThanOrEqual(canvas!.x - 1)
      expect(b.y, `${b.id} top`).toBeGreaterThanOrEqual(canvas!.y - 1)
      expect(b.x + b.w, `${b.id} right`).toBeLessThanOrEqual(canvas!.x + canvas!.width + 1)
      expect(b.y + b.h, `${b.id} bottom`).toBeLessThanOrEqual(canvas!.y + canvas!.height + 1)
    }
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j]
        const overlap = a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h
        expect(overlap, `${a.id} overlaps ${b.id}`).toBe(false)
      }
    }
  })

  test('the engine compiles the starter once', async ({ board }) => {
    const before = await board.qa.compileCount()
    await loadStarter(board, STARTER)
    expect(await board.qa.settled()).toBe(before + 1)
    await expect(board.page.getByTestId('engine-error')).toHaveCount(0)
    expect((await board.qa.engineStatus()).error).toBe('')
  })

  test('playing the starter gives a stereo reading and a spectrum', async ({ board }) => {
    await loadStarter(board, STARTER)
    await board.qa.settled()
    await board.qa.loadSyntheticClip(4)
    await board.page.locator('[data-test="play"]').click()
    await board.page.waitForTimeout(3000)
    await expect.poll(async () => (await board.qa.monitor()).corr, { timeout: 15_000 }).not.toBeNull()
    const m = await board.qa.monitor()
    expect(Number.isFinite(m.corr)).toBe(true)
    expect(m.bands.filter((v) => v !== null).length).toBeGreaterThan(5)
    // Stereo pedals in this chain make the two sides differ.
    expect(m.corr!).toBeLessThan(0.9999)
  })

  test('a knob changes the value but never recompiles', async ({ board }) => {
    await loadStarter(board, STARTER)
    const count = await board.qa.settled()
    const field = board.page.locator('[data-testid^="ctrl-highpass-"][type="number"]').first()
    const id = (await field.getAttribute('data-testid'))!
    const key = id.replace(/^ctrl-/, '').replace('-', '_')
    const before = await board.qa.paramValue(key)
    expect(before).toBeDefined()
    const max = Number(await field.getAttribute('max'))
    const min = Number(await field.getAttribute('min'))
    const target = before === max ? min : max
    await field.fill(String(target))
    await field.press('Enter')
    await expect.poll(() => board.qa.paramValue(key)).toBe(target)
    await board.page.waitForTimeout(DEBOUNCE_MARGIN_MS)
    expect(await board.qa.compileCount()).toBe(count)
  })

  test('adding and wiring a pedal recompiles exactly once; a burst of loads also once', async ({ board }) => {
    const c0 = await board.qa.compileCount()
    await addPedal(board, 'highpass')
    await wire(board.page, 'input', 'highpass1')
    // Still invalid (the pedal feeds nothing), so nothing compiles yet.
    await board.page.waitForTimeout(DEBOUNCE_MARGIN_MS)
    expect(await board.qa.compileCount()).toBe(c0)
    await wire(board.page, 'highpass1', 'output')
    await expect(board.page.locator('.vue-flow__edge')).toHaveCount(2)
    const count = await board.qa.settled()
    expect(count).toBe(c0 + 1)
    // Two structural changes inside one debounce window collapse into a single compile.
    await board.page.evaluate(() => {
      const qa = (window as any).__pedalboard
      qa.loadStarterBySlug('clean')
      qa.loadStarterBySlug('rt-tech-priest-pasqal-target-stereo')
    })
    expect(await board.qa.settled()).toBe(count + 1)
  })

  test('a second wire into a taken input is refused with a reason', async ({ board }) => {
    await loadStarter(board, 'clean')
    await board.qa.settled()
    await addPedal(board, 'highpass')
    await wire(board.page, 'highpass1', 'output')
    await expect(board.page.getByTestId('refusal')).toContainText(/already has a wire/i)
    expect((await board.qa.graph()).edges).toHaveLength(1)
  })

  test('the stomp switch bypasses and restores a pedal', async ({ board }) => {
    await loadStarter(board, STARTER)
    await board.qa.settled()
    const key = await board.qa.stompKey('highpass')
    expect(await board.qa.paramValue(key)).toBe(1)
    await board.page.getByTestId('stomp-highpass').click()
    await expect.poll(() => board.qa.paramValue(key)).toBe(0)
    await board.page.getByTestId('stomp-highpass').click()
    await expect.poll(() => board.qa.paramValue(key)).toBe(1)
  })
})
