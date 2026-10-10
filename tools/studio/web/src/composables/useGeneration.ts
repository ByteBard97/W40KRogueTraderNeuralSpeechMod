import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api/client'
import type { CloneRequest } from '../api/types'
import { useModelStore } from '../stores/model'
import { isMissingRoute, useWorkbenchJobsStore } from '../stores/workbenchJobs'
import { runBatch } from '../utils/batch'
import { pickSeed } from '../utils/seed'
import { seedsFor } from '../utils/seedPolicy'
import { useSpeakerContext } from './useSpeakerContext'
import type { SpeakerContext } from './useSpeakerState'
import { useToasts } from './useToasts'

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

/** Mount once per speaker page: follows this speaker's server jobs, so a batch started earlier shows up again after leaving the page. */
export function useJobWatch(ctx: SpeakerContext) {
  const jobs = useWorkbenchJobsStore()
  onMounted(() => { void jobs.attach(ctx.slug, (t) => ctx.upsertTake(t)) })
  onBeforeUnmount(() => jobs.detach(ctx.slug))
}

/** Clone takes for every ticked line x ticked source, as one server job (or, on a server without a job queue, one request at a time). */
export function useCloneGeneration() {
  const ctx = useSpeakerContext()
  const model = useModelStore()
  const jobs = useWorkbenchJobsStore()
  const toasts = useToasts()
  const syncRunning = ref(false)
  const syncStatus = ref('')
  let stopSync = false
  onBeforeUnmount(() => { stopSync = true })     // a fallback batch must not keep the model busy after the page is gone

  const chosenLines = computed(() => ctx.lines.value.filter((l) => ctx.selectedLines.value.has(l.guid)))
  const total = computed(() => chosenLines.value.length * ctx.chosenSources.value.length)
  const activeJobs = computed(() => jobs.activeFor(ctx.slug, 'clone'))
  const running = computed(() => syncRunning.value || activeJobs.value.length > 0)
  const modelOk = computed(() => model.state === 'ready' || (model.state === 'busy' && activeJobs.value.length > 0))
  const blocked = computed(() => (!total.value ? 'Tick a source and some lines first.' : !modelOk.value ? model.reason : ''))
  const problem = computed(() => jobs.problem[ctx.slug] ?? '')
  /** Mean seconds per past take times the takes asked for; unknown until the speaker has any takes. */
  const estimateS = computed(() => {
    const secs = ctx.takes.value.map((t) => t.seconds).filter((s) => typeof s === 'number' && s > 0)
    return secs.length && total.value ? Math.round((secs.reduce((a, b) => a + b, 0) / secs.length) * total.value) : null
  })

  function requests(): CloneRequest[] {
    const seeds = seedsFor(ctx.seedPolicy.value, ctx.options.value.seed, chosenLines.value.length)
    return chosenLines.value.flatMap((l, i) =>
      ctx.chosenSources.value.map((src) => ({
        guid: l.guid, text: l.text, instruct: l.instruct, reference: { wav: src.wav, text: src.text }, options: { ...ctx.options.value, seed: seeds[i] },
      })),
    )
  }

  async function generateSync() {
    syncRunning.value = true
    stopSync = false
    let i = 0
    const policy = ctx.seedPolicy.value
    const seed = policy === 'fixed' ? ctx.options.value.seed : policy === 'one' ? pickSeed('') : ''
    const res = await runBatch({
      lines: chosenLines.value, sources: ctx.chosenSources.value, options: { ...ctx.options.value, seed }, shouldStop: () => stopSync,
      generate: (req) => { syncStatus.value = `Generating ${++i} of ${total.value}…`; return api.cloneGenerate(ctx.slug, req) },
      onTake: async (t) => {
        ctx.upsertTake(t)
        if (!ctx.fxChosen.value.length) return
        try {
          ctx.upsertTake(await api.takeFx(ctx.slug, t.id, ctx.fxChosen.value))
        } catch (e) {
          toasts.error(message(e))
        }
      },
    })
    syncStatus.value = `Done, ${res.done} takes.`
    if (res.error) toasts.error(res.error)
    syncRunning.value = false
  }

  async function generate() {
    if (blocked.value || syncRunning.value) return
    try {
      await jobs.submit(ctx.slug, 'clone', requests(), { fx: ctx.fxChosen.value, label: 'Generating' })
    } catch (e) {
      if (isMissingRoute(e)) await generateSync()
      else toasts.error(message(e))
    }
  }

  /** Cancel what is queued and drop the take in flight when it lands (the model cannot abort a running generation). */
  async function cancelAll() {
    stopSync = true
    await Promise.all(activeJobs.value.map((j) => jobs.cancel(ctx.slug, j.id).catch((e) => toasts.error(message(e)))))
  }
  const cancel = (id: string) => jobs.cancel(ctx.slug, id).catch((e) => toasts.error(message(e)))

  return { chosenLines, total, activeJobs, running, syncRunning, syncStatus, blocked, problem, estimateS, generate, cancelAll, cancel }
}

export interface DesignRequest { description: string; seed: string; cfg: number; timesteps: number }

/** Live design takes as server jobs (falling back to a synchronous request when the server has no job queue). */
export function useDesignGeneration() {
  const ctx = useSpeakerContext()
  const model = useModelStore()
  const jobs = useWorkbenchJobsStore()
  const toasts = useToasts()
  const syncBusy = ref(false)

  const activeJobs = computed(() => jobs.activeFor(ctx.slug, 'design'))
  const busy = computed(() => syncBusy.value || activeJobs.value.length > 0)
  const blocked = computed(() => (model.state === 'ready' || (model.state === 'busy' && activeJobs.value.length > 0) ? '' : model.reason))

  async function generate(req: DesignRequest, onSync: (t: Awaited<ReturnType<typeof api.designGenerate>>) => void) {
    if (blocked.value) return
    try {
      await jobs.submit(ctx.slug, 'design', [{ ...req, seed: req.seed.trim() }], { label: 'Designing' })
    } catch (e) {
      if (!isMissingRoute(e)) return void toasts.error(message(e))
      syncBusy.value = true
      try {
        onSync(await api.designGenerate(ctx.slug, { ...req, seed: req.seed.trim() }))
      } catch (err) {
        toasts.error(message(err))
      } finally {
        syncBusy.value = false
      }
    }
  }
  const cancel = (id: string) => jobs.cancel(ctx.slug, id).catch((e) => toasts.error(message(e)))

  return { activeJobs, busy, blocked, generate, cancel }
}
