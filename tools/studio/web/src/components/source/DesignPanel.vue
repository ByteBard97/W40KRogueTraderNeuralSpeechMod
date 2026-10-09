<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../../api/client'
import type { LiveTake } from '../../api/types'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useModelStore } from '../../stores/model'
import CandidateRanker from './CandidateRanker.vue'

const DEFAULT_CFG = 2
const DEFAULT_STEPS = 10
const ctx = useSpeakerContext()
const model = useModelStore()
const { play } = useAudioPlayer()

const description = ref(ctx.detail.value?.design?.description ?? '')
// ctx.load() replaces the detail after Keep, verdicts and reorders; keep the box in step with the saved description.
watch(() => ctx.detail.value?.design?.description, (d) => { if (d !== undefined) description.value = d })
const seed = ref('')
const cfg = ref(DEFAULT_CFG)
const steps = ref(DEFAULT_STEPS)
const busy = ref(false)
const error = ref('')
const takes = ref<LiveTake[]>([])

async function generate() {
  busy.value = true
  error.value = ''
  try {
    takes.value.unshift(await api.designGenerate(ctx.slug, { description: description.value, seed: seed.value.trim(), cfg: cfg.value, timesteps: steps.value }))
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
/** Run a design action, then refresh only the speaker detail; failures are shown instead of lost. */
async function act(fn: () => Promise<unknown>) {
  error.value = ''
  try {
    await fn()
    await ctx.refreshDetail()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
const keeping = new Set<LiveTake>()
const keep = async (t: LiveTake) => {
  if (keeping.has(t)) return        // a double-click must not keep the same take twice
  keeping.add(t)
  await act(async () => {
    await api.designKeep(ctx.slug, t)
    takes.value = takes.value.filter((x) => x !== t)
  })
  keeping.delete(t)
}
const verdict = (v: Parameters<typeof api.designVerdict>[1]) => act(() => api.designVerdict(ctx.slug, v))
const reorder = (order: string[]) => act(() => api.designOrder(ctx.slug, order))
/** Saving writes the real overrides.json, so only a real change counts: not a focus-and-leave, not an empty box. */
function saveDescription() {
  const text = description.value.trim()
  if (!text || text === ctx.detail.value?.design?.description) return
  void act(() => api.designDescription(ctx.slug, text))
}
</script>

<template>
  <div v-if="ctx.detail.value?.design">
    <textarea v-model="description" rows="2" @blur="saveDescription" />
    <div class="live">
      <b>Live design</b>
      seed <input data-seed v-model="seed" placeholder="random" />
      cfg <input type="number" step="0.5" v-model.number="cfg" />
      steps <input type="number" v-model.number="steps" />
      <button data-generate class="primary" :disabled="!model.ready || busy" :title="model.reason" @click="generate">{{ busy ? 'generating…' : 'Generate' }}</button>
      <span v-if="!model.ready" class="dim">{{ model.reason }}</span>
      <span v-if="error" class="err">{{ error }}</span>
      <div v-for="t in takes" :key="t.file" class="take">
        <button class="play" @click="play(`data/voice_design/${t.file}`)">▶</button>
        <button data-seed-chip class="chip" title="reuse this seed" @click="seed = String(t.seed)">seed {{ t.seed }}</button>
        <span class="dim">cfg {{ t.cfg }} · {{ t.timesteps }} steps · {{ t.seconds }}s</span>
        <button data-keep @click="keep(t)">Keep</button>
      </div>
    </div>
    <CandidateRanker :candidates="ctx.detail.value.design.candidates" :order="ctx.detail.value.design.order" @reorder="reorder" @verdict="verdict" />
  </div>
</template>

<style scoped>
textarea { width: 100%; }
.live { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; margin: 8px 0; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.live input { width: 84px; }
.take { width: 100%; display: flex; gap: 8px; align-items: center; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border-radius: 10px; padding: 0 8px; font-size: 12px; color: var(--acc); cursor: pointer; }
.primary { background: var(--acc); color: var(--on-acc); border-color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); font-size: 13px; }
</style>
