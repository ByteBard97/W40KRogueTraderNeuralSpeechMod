import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { lineFixture, optionsFixture, recipeFixture, takeFixture } from '../test-utils/labFixtures'

vi.mock('../api/client', () => ({
  api: { labOptions: vi.fn(), labSpeakers: vi.fn(), labRecipes: vi.fn(), labLines: vi.fn(), labPrepare: vi.fn(), labTakes: vi.fn(), labTakeUpdate: vi.fn(), labRecipeSave: vi.fn(), labLexicon: vi.fn() },
}))

import { useLabStore } from './lab'

const SPEAKER = 'Vladaym Tocara the Liege'
const prepared = { stages: [{ name: 'source', text: 'x' }], pieces: [{ text: 'x', kind: 'whole', gap_ms: null, display: 'x' }], recipe: recipeFixture() }

function wire() {
  vi.mocked(api.labOptions).mockResolvedValue(optionsFixture())
  vi.mocked(api.labSpeakers).mockResolvedValue([{ speaker: SPEAKER, slug: 'v', lines: 3, chars: 100 }])
  vi.mocked(api.labRecipes).mockResolvedValue([recipeFixture()])
  vi.mocked(api.labLines).mockResolvedValue({ speaker: SPEAKER, ref: { wav: 'data/ref.wav' }, lines: [lineFixture('a', 0, 14), lineFixture('b', 1, 9, 'overdriven'), lineFixture('c', 2, 15, 'clipped')] })
  vi.mocked(api.labPrepare).mockResolvedValue(prepared)
  vi.mocked(api.labTakes).mockResolvedValue([takeFixture('t1')])
}

describe('lab store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    wire()
  })

  it('loads options, recipes and lines, and selects the first line', async () => {
    const lab = useLabStore()
    await lab.init()
    expect(lab.recipe).toEqual(recipeFixture())
    expect(lab.selectedGuid).toBe('a')
    expect(api.labLines).toHaveBeenCalledWith(SPEAKER)
    expect(api.labPrepare).toHaveBeenCalledWith({ speaker: SPEAKER, guid: 'a', recipe: recipeFixture() })
    expect(lab.takes).toHaveLength(1)
  })

  it('sorts worst first and filters flagged', async () => {
    const lab = useLabStore()
    await lab.init()
    lab.sort = 'worst'
    expect(lab.visible.map((l) => l.guid)).toEqual(['b', 'a', 'c'])
    lab.filter = 'flagged'
    expect(lab.visible.map((l) => l.guid)).toEqual(['b', 'c'])
  })

  it('checks lines, selects all flagged and clears', async () => {
    const lab = useLabStore()
    await lab.init()
    lab.toggleCheck('a')
    lab.toggleCheck('a')
    expect(lab.checked).toEqual([])
    lab.checkFlagged()
    expect(lab.checked).toEqual(['b', 'c'])
    lab.clearChecked()
    expect(lab.checked).toEqual([])
  })

  it('resets to the production recipe, leaving it untouched by edits', async () => {
    const lab = useLabStore()
    await lab.init()
    lab.recipe!.cfg = 2
    expect(lab.recipes[0].cfg).toBe(3)
    lab.resetRecipe()
    expect(lab.recipe!.cfg).toBe(3)
  })

  it('loads a take recipe as a copy', async () => {
    const lab = useLabStore()
    await lab.init()
    const t = takeFixture('t2', { recipe: { ...recipeFixture(), cfg: 1.5 } })
    lab.loadRecipe(t.recipe)
    lab.recipe!.cfg = 9
    expect(t.recipe.cfg).toBe(1.5)
  })

  it('ignores a slow prepare answer that was overtaken', async () => {
    const lab = useLabStore()
    await lab.init()
    let release!: (v: typeof prepared) => void
    vi.mocked(api.labPrepare).mockReturnValueOnce(new Promise((r) => (release = r)))
    const slow = lab.prepare()
    vi.mocked(api.labPrepare).mockResolvedValueOnce({ ...prepared, stages: [{ name: 'source', text: 'new' }] })
    await lab.prepare()
    release({ ...prepared, stages: [{ name: 'source', text: 'old' }] })
    await slow
    expect(lab.prepared!.stages[0].text).toBe('new')
  })

  it('saves a recipe by name and keeps it selected', async () => {
    const lab = useLabStore()
    await lab.init()
    vi.mocked(api.labRecipeSave).mockResolvedValue([recipeFixture(), { ...recipeFixture(), name: 'try1' }])
    await lab.saveRecipe(' try1 ')
    expect(api.labRecipeSave).toHaveBeenCalledWith('try1', expect.objectContaining({ name: 'try1' }))
    expect(lab.recipes).toHaveLength(2)
    expect(lab.recipe!.name).toBe('try1')
  })

  it('rates and hides takes', async () => {
    const lab = useLabStore()
    await lab.init()
    vi.mocked(api.labTakeUpdate).mockResolvedValue(takeFixture('t1', { rating: 4 }))
    await lab.updateTake('t1', { rating: 4 })
    expect(lab.takes[0].rating).toBe(4)
    await lab.updateTake('t1', { hidden: true })
    expect(lab.takes).toEqual([])
  })

  it('shows an error from the server', async () => {
    vi.mocked(api.labLines).mockRejectedValue(new Error('no cast lines'))
    const lab = useLabStore()
    await lab.init()
    expect(lab.error).toBe('no cast lines')
  })
})
