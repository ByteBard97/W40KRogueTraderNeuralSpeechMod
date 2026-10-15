import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { LabLexiconHit, LabLine, LabLines, LabOptions, LabPrepared, LabRecipe, LabSpeaker, LabTake } from '../api/labTypes'
import { cloneRecipe, filterLines, isFlagged, sortLines, type LineFilter, type LineSort } from '../utils/labRecipe'

export const DEFAULT_SPEAKER = 'Vladaym Tocara the Liege'
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export const useLabStore = defineStore('lab', () => {
  const options = ref<LabOptions | null>(null)
  const speakers = ref<LabSpeaker[]>([])
  const speaker = ref<string>(DEFAULT_SPEAKER)
  const data = ref<LabLines | null>(null)
  const selectedGuid = ref<string | null>(null)
  const checked = ref<string[]>([])
  const filter = ref<LineFilter>('all')
  const sort = ref<LineSort>('order')
  const query = ref('')
  const recipe = ref<LabRecipe | null>(null)
  const recipes = ref<LabRecipe[]>([])
  const prepared = ref<LabPrepared | null>(null)
  const takes = ref<LabTake[]>([])
  const error = ref<string | null>(null)
  const loading = ref(false)
  const preparing = ref(false)
  let prepareSeq = 0
  let takesSeq = 0
  let linesSeq = 0

  const lines = computed<LabLine[]>(() => data.value?.lines ?? [])
  const ref_ = computed(() => data.value?.ref ?? null)
  const visible = computed(() => sortLines(filterLines(lines.value, filter.value, query.value), sort.value))
  const selected = computed(() => lines.value.find((l) => l.guid === selectedGuid.value) ?? null)
  const flaggedGuids = computed(() => lines.value.filter((l) => isFlagged(l.current)).map((l) => l.guid))
  const production = computed(() => recipes.value[0] ?? options.value?.default_recipe ?? null)

  async function guarded(fn: () => Promise<void>) {
    error.value = null
    try {
      await fn()
    } catch (e) {
      error.value = msg(e)
    }
  }

  async function init() {
    loading.value = true
    await guarded(async () => {
      const [opts, sp, rs] = await Promise.all([api.labOptions(), api.labSpeakers(), api.labRecipes()])
      options.value = opts
      speakers.value = sp
      recipes.value = rs
      recipe.value = cloneRecipe(rs[0] ?? opts.default_recipe)
      if (!sp.some((s) => s.speaker === speaker.value) && sp.length) speaker.value = sp[0].speaker
      await loadLines()
    })
    loading.value = false
  }

  async function loadLines() {
    const seq = ++linesSeq
    const d = await api.labLines(speaker.value)
    if (seq !== linesSeq) return
    data.value = d
    checked.value = checked.value.filter((g) => d.lines.some((l) => l.guid === g))
    if (!d.lines.some((l) => l.guid === selectedGuid.value)) selectedGuid.value = null
    if (!selectedGuid.value && d.lines.length) await select(sortLines(d.lines, 'order')[0].guid)
  }

  async function pickSpeaker(name: string) {
    speaker.value = name
    selectedGuid.value = null
    checked.value = []
    takes.value = []
    prepared.value = null
    await guarded(loadLines)
  }

  async function select(guid: string) {
    selectedGuid.value = guid
    await Promise.all([loadTakes(), prepare()])
  }

  function toggleCheck(guid: string) {
    checked.value = checked.value.includes(guid) ? checked.value.filter((g) => g !== guid) : [...checked.value, guid]
  }
  const checkFlagged = () => (checked.value = [...flaggedGuids.value])
  const clearChecked = () => (checked.value = [])

  /** Run the text stages for the selected line; a slower earlier answer never overwrites a newer one. */
  async function prepare() {
    if (!selectedGuid.value || !recipe.value) return
    const seq = ++prepareSeq
    preparing.value = true
    try {
      const out = await api.labPrepare({ speaker: speaker.value, guid: selectedGuid.value, recipe: recipe.value })
      if (seq === prepareSeq) prepared.value = out
    } catch (e) {
      if (seq === prepareSeq) error.value = msg(e)
    } finally {
      if (seq === prepareSeq) preparing.value = false
    }
  }

  async function loadTakes() {
    if (!selectedGuid.value) return
    const seq = ++takesSeq
    const guid = selectedGuid.value
    await guarded(async () => {
      const t = await api.labTakes(speaker.value, guid)
      if (seq === takesSeq) takes.value = t
    })
  }

  /** Reload the lines too: a fresh render does not change them, but the metrics cache may have filled in. */
  async function refreshLines() {
    await guarded(async () => {
      const d = await api.labLines(speaker.value)
      data.value = d
    })
  }

  function loadRecipe(r: LabRecipe) {
    recipe.value = cloneRecipe(r)
  }
  const resetRecipe = () => production.value && loadRecipe(production.value)

  async function saveRecipe(name: string) {
    if (!recipe.value || !name.trim()) return
    await guarded(async () => {
      recipes.value = await api.labRecipeSave(name.trim(), { ...recipe.value!, name: name.trim() })
      recipe.value = { ...recipe.value!, name: name.trim() }
    })
  }

  async function updateTake(id: string, body: { rating?: number; note?: string; hidden?: boolean }) {
    await guarded(async () => {
      const t = await api.labTakeUpdate(speaker.value, id, body)
      takes.value = body.hidden ? takes.value.filter((x) => x.id !== id) : takes.value.map((x) => (x.id === id ? { ...x, ...t } : x))
    })
  }

  async function lexicon(q: string): Promise<LabLexiconHit[]> {
    try {
      return await api.labLexicon(q)
    } catch (e) {
      error.value = msg(e)
      return []
    }
  }

  return {
    options, speakers, speaker, data, selectedGuid, checked, filter, sort, query, recipe, recipes, prepared, takes, error, loading, preparing,
    lines, ref: ref_, visible, selected, flaggedGuids, production,
    init, loadLines, pickSpeaker, select, toggleCheck, checkFlagged, clearChecked, prepare, loadTakes, refreshLines, loadRecipe, resetRecipe, saveRecipe, updateTake, lexicon,
  }
})
