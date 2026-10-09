<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../../api/client'
import type { Line, Take } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import ClipCompare from '../shared/ClipCompare.vue'
import StarRating from '../shared/StarRating.vue'

const props = defineProps<{ take: Take; line: Line | null }>()
const ctx = useSpeakerContext()
const error = ref('')
const busy = ref(false)

const clips = computed(() => [
  { key: 'source', label: 'source clip', path: props.take.reference },
  { key: 'bank', label: 'bank', path: props.line?.baseline ?? null },
  { key: 'raw', label: 'raw clone', path: props.take.raw },
  { key: 'fx', label: 'fx', path: props.take.fx ? `${props.take.fx.wav}?v=${props.take.fx.v}` : null },
])
const source = computed(() => (props.take.reference.split('/').pop() ?? '').replace('.wav', ''))
// The picker wins; with an empty picker, "re-apply" repeats the take's own presets. An empty list would clear the FX.
const presetsToApply = computed(() => (ctx.fxChosen.value.length ? ctx.fxChosen.value : props.take.fx?.presets ?? []))
const canApply = computed(() => presetsToApply.value.length > 0)

async function rate(n: number) {
  ctx.upsertTake(await api.takeRate(ctx.slug, props.take.id, { rating: n }))
}
async function applyFx(presets: string[] = presetsToApply.value) {
  busy.value = true
  error.value = ''
  try {
    ctx.upsertTake(await api.takeFx(ctx.slug, props.take.id, presets))
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="take">
    <ClipCompare :clips="clips" />
    <button data-fx :disabled="!canApply || busy" @click="applyFx()">{{ take.fx ? 're-apply FX' : 'apply FX' }}</button>
    <button v-if="take.fx" data-clear-fx :disabled="busy" @click="applyFx([])">clear FX</button>
    <span class="dim">{{ source }} · seed {{ take.seed }} · cfg {{ take.options.cfg }} · {{ take.options.timesteps }} steps · {{ take.audio_s ?? '?' }}s audio</span>
    <StarRating :model-value="take.rating" @update:model-value="rate" />
    <span v-if="error" class="err">{{ error }}</span>
  </div>
</template>

<style scoped>
.take { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 4px 0; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); font-size: 13px; }
</style>
