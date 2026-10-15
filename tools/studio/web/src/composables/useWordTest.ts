import { computed, onScopeDispose, ref } from 'vue'
import { api } from '../api/client'
import type { LabPronMode, LabTake } from '../api/labTypes'
import { useLabStore } from '../stores/lab'
import { seedsFor, carrierSentence, DEFAULT_CARRIER, variantLabel, variantRecipe } from '../utils/labRecipe'
import { runRender } from './useLabRender'

export interface WordVariant { id: number; mode: LabPronMode; value: string }
export interface WordResult { label: string; take: LabTake | null; error: string | null }

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Render one word in a carrier sentence under several pronunciation variants, all with the same seed. */
export function useWordTest() {
  const lab = useLabStore()
  const word = ref('von Valancius')
  const carrier = ref(DEFAULT_CARRIER)
  const variants = ref<WordVariant[]>([{ id: 1, mode: 'plain', value: '' }])
  const results = ref<WordResult[]>([])
  const progress = ref({ done: 0, total: 0 })
  const running = ref(false)
  const error = ref<string | null>(null)
  let nextId = 2
  let gone = false
  onScopeDispose(() => (gone = true))

  const canRun = computed(() => !running.value && word.value.trim() !== '' && carrier.value.includes('{w}') && variants.value.length > 0 && !!lab.recipe && !!lab.ref)

  const addVariant = () => variants.value.push({ id: nextId++, mode: 'plain', value: '' })
  const removeVariant = (id: number) => (variants.value = variants.value.filter((v) => v.id !== id))

  async function run(rng?: () => number) {
    if (!canRun.value || !lab.recipe) return
    running.value = true
    error.value = null
    results.value = []
    const base = lab.recipe
    const [seed] = seedsFor(base, 1, rng)
    const text = carrierSentence(carrier.value, word.value.trim())
    progress.value = { done: 0, total: variants.value.length }
    try {
      for (const v of variants.value) {
        if (gone) break
        const label = variantLabel(v)
        try {
          const recipe = variantRecipe(base, word.value.trim(), v)
          const job = await runRender({ speaker: lab.speaker, items: [{ text, label }], recipe, seeds: [seed], ref: lab.ref ?? undefined }, { stopped: () => gone })
          if (job.state === 'error') throw new Error(job.error ?? 'render failed')
          const all = await api.labTakes(lab.speaker)
          results.value.push({ label, take: all.find((t) => job.take_ids.includes(t.id)) ?? null, error: null })
        } catch (e) {
          results.value.push({ label, take: null, error: msg(e) })
        }
        progress.value = { ...progress.value, done: progress.value.done + 1 }
      }
    } finally {
      running.value = false
    }
  }

  return { word, carrier, variants, results, progress, running, error, canRun, addVariant, removeVariant, run }
}
