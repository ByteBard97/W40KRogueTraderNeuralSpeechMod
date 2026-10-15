import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, loadStarter, STARTER, test } from './fixtures'

const NAME = 'e2e-save-roundtrip'

test('save writes only the temp root, and the graph loads back the same', async ({ board }) => {
  const root = process.env.E2E_ROOT!
  expect(root).toContain('rt-studio-e2e-')
  await loadStarter(board, STARTER)
  await board.qa.settled()
  const before = await board.qa.graph()

  await board.page.getByTestId('name-input').fill(NAME)
  await board.page.getByTestId('save-btn').click()
  const graphFile = join(root, 'data/fx_lab/graphs', `${NAME}.json`)
  await expect.poll(() => existsSync(graphFile)).toBe(true)
  expect(existsSync(join(root, 'tools/fx_lab/faust/presets', `${NAME}.dsp`))).toBe(true)
  const presets = JSON.parse(readFileSync(join(root, 'data/fx_lab/presets.json'), 'utf-8'))
  expect(presets[NAME].graph.nodes).toHaveLength(14)
  expect(presets[NAME].dsp).toBe(`presets/${NAME}.dsp`)

  await board.page.reload()
  await expect(board.page.getByTestId('palette')).toBeVisible()
  await board.page.getByTestId('preset-saved').click()
  await board.page.getByTestId(`saved-${NAME}`).click()
  await expect(board.page.locator('.vue-flow__node')).toHaveCount(14)
  const after = await board.qa.graph()
  const shape = (g: typeof before) => ({
    nodes: g.nodes.map((n) => n.id).sort(),
    edges: g.edges.map((e) => `${e.source}>${e.target}.${e.targetPort}`).sort(),
  })
  expect(shape(after)).toEqual(shape(before))
  await expect(board.page.locator('.vue-flow__edge')).toHaveCount(13)
})
