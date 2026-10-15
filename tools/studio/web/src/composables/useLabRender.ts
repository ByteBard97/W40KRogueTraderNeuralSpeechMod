import { computed, onScopeDispose, ref } from 'vue'
import { api } from '../api/client'
import type { LabJob, LabRenderItem } from '../api/labTypes'
import { useLabStore } from '../stores/lab'
import { buildRenderBody, MAX_SEEDS, MIN_SEEDS } from '../utils/labRecipe'
import { isTerminal, pollJob, type PollOptions } from '../utils/labJob'

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Start a render job and follow it to the end. Shared by the line renders and the word test. */
export async function runRender(body: Parameters<typeof api.labRender>[0], opts: PollOptions = {}): Promise<LabJob> {
  return pollJob(api.labJob, await api.labRender(body), opts)
}

/** Render the selected / checked lines with the current recipe, track the job, refresh the takes when it ends. */
export function useLabRender() {
  const lab = useLabStore()
  const seedCount = ref(MIN_SEEDS)
  const job = ref<LabJob | null>(null)
  const error = ref<string | null>(null)
  let gone = false
  onScopeDispose(() => (gone = true))

  const running = computed(() => !!job.value && !isTerminal(job.value))
  const percent = computed(() => (job.value && job.value.total ? Math.round((job.value.done / job.value.total) * 100) : 0))

  async function start(items: LabRenderItem[]) {
    if (!lab.recipe || !items.length || running.value) return
    error.value = null
    try {
      const body = buildRenderBody({ speaker: lab.speaker, items, recipe: lab.recipe, seedCount: seedCount.value, ref: lab.ref })
      const final = await runRender(body, { onUpdate: (j) => (job.value = j), stopped: () => gone })
      job.value = final
      if (final.state === 'error') error.value = final.error ?? 'The render failed.'
      await Promise.all([lab.loadTakes(), lab.refreshLines()])
    } catch (e) {
      error.value = msg(e)
      job.value = null
    }
  }

  const renderSelected = () => (lab.selectedGuid ? start([{ guid: lab.selectedGuid }]) : Promise.resolve())
  const renderChecked = () => start(lab.checked.map((guid) => ({ guid })))
  async function cancel() {
    if (!job.value || !running.value) return
    try {
      job.value = await api.labJobCancel(job.value.id)
    } catch (e) {
      error.value = msg(e)
    }
  }
  const setSeedCount = (n: number) => (seedCount.value = Math.min(MAX_SEEDS, Math.max(MIN_SEEDS, Math.floor(n) || MIN_SEEDS)))

  return { seedCount, job, error, running, percent, renderSelected, renderChecked, cancel, setSeedCount }
}
