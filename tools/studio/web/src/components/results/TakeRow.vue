<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../../api/client'
import type { Line, Take } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useToasts } from '../../composables/useToasts'
import { isTypingTarget } from '../../utils/keys'
import Btn from '../ui/Btn.vue'
import SavedIndicator from '../ui/SavedIndicator.vue'
import StarScore from './StarScore.vue'
import TakeCompare from './TakeCompare.vue'

const MAX_RATING = 5
const props = defineProps<{ take: Take; line: Line | null }>()
const ctx = useSpeakerContext()
const router = useRouter()
const toasts = useToasts()
const busy = ref(false)
const saved = ref(false)

const speaker = computed(() => ctx.detail.value?.summary.name ?? '')
const source = computed(() => (props.take.reference.split('/').pop() ?? '').replace('.wav', ''))
// The picker wins; with an empty picker, "re-apply" repeats the take's own presets. An empty list would clear the FX.
const presetsToApply = computed(() => (ctx.fxChosen.value.length ? ctx.fxChosen.value : props.take.fx?.presets ?? []))
const canApply = computed(() => presetsToApply.value.length > 0)

async function rate(n: number) {
  try {
    ctx.upsertTake(await api.takeRate(ctx.slug, props.take.id, { rating: n }))
    saved.value = true
  } catch (e) {
    toasts.error(e instanceof Error ? e.message : String(e))
  }
}
async function applyFx(presets: string[] = presetsToApply.value) {
  busy.value = true
  try {
    ctx.upsertTake(await api.takeFx(ctx.slug, props.take.id, presets))
  } catch (e) {
    toasts.error(e instanceof Error ? e.message : String(e), () => void applyFx(presets))
  } finally {
    busy.value = false
  }
}
function onKey(e: KeyboardEvent) {
  const n = Number(e.key)
  if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target) || !Number.isInteger(n) || n < 0 || n > MAX_RATING) return
  e.preventDefault()
  void rate(n)
}
</script>

<template>
  <div class="take" tabindex="0" :data-take="take.id" @keydown="onKey">
    <TakeCompare :take="take" :line="line" :speaker="speaker" />
    <div class="rate">
      <StarScore :model-value="take.rating" label="Take rating" @update:model-value="rate" />
      <SavedIndicator v-if="saved && take.rating" class="push" />
      <span v-else-if="!take.rating" class="muted small">Not rated · 1–5</span>
    </div>
    <div class="meta muted num">{{ source }} · seed {{ take.seed }} · cfg {{ take.options.cfg }} · {{ take.options.timesteps }} steps</div>
    <div class="acts">
      <Btn size="sm" data-fx :disabled="!canApply || busy" @click="applyFx()">{{ take.fx ? 'Re-apply FX' : 'Apply FX' }}</Btn>
      <Btn v-if="take.fx" size="sm" variant="ghost" data-clear-fx :disabled="busy" @click="applyFx([])">Clear FX</Btn>
      <Btn size="sm" variant="ghost" data-open-fx title="Open this take in the FX Lab" @click="router?.push({ path: '/fx', query: { clip: take.raw } })">Open in FX Lab</Btn>
    </div>
  </div>
</template>

<style scoped>
.take { display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-2) 0; border-radius: var(--r-md); }
.rate { display: flex; align-items: center; gap: var(--s-2); }
.push { margin-left: auto; }
.small { font-size: var(--fs-sm); }
.meta { font-size: var(--fs-xs); overflow-wrap: anywhere; }
.acts { display: flex; flex-wrap: wrap; gap: var(--s-1); }
</style>
