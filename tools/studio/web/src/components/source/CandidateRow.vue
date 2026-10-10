<script setup lang="ts">
import { computed } from 'vue'
import type { Candidate, CloneTest, Verdict } from '../../api/types'
import { shortId } from '../../composables/useDesign'
import { isTypingTarget } from '../../utils/keys'
import StarScore from '../results/StarScore.vue'
import Btn from '../ui/Btn.vue'
import Flag from '../ui/Flag.vue'
import Icon from '../ui/Icon.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import ScoreChip from '../ui/ScoreChip.vue'
import Seg from '../ui/Seg.vue'
import Tag from '../ui/Tag.vue'
import ClonePill from './ClonePill.vue'

const ACCENTS = [
  { value: 'british', label: 'British' },
  { value: 'american', label: 'American' },
  { value: 'other', label: 'Other' },
]
const ACCENT_KEYS: Record<string, 'british' | 'american' | 'other'> = { b: 'british', a: 'american', o: 'other' }
const US_THRESHOLD = 0.5

const props = defineProps<{
  cand: Candidate
  rank: number
  picked: boolean
  isSource: boolean
  clones: CloneTest[]
  /** Shown first in the player bar ("Governor Ruoldo · c2"). */
  speaker: string
  first: boolean
  last: boolean
  /** Whether "Render 2 clone tests" can run on this server. */
  canRenderTests: boolean
}>()
const emit = defineEmits<{
  verdict: [patch: Verdict]
  pick: []
  reject: []
  move: [delta: -1 | 1]
  source: [on: boolean]
}>()

const id = computed(() => shortId(props.cand.id))
const rejected = computed(() => !!props.cand.verdict.reject)
const sc = computed(() => props.cand.scores)
const hasSeed = computed(() => props.cand.gen?.seed !== undefined)
const testLabel = (c: CloneTest) => c.text || 'clone test'

/** Digits act on the focused row: 1-5 fit, Shift+1-5 accent score. Letters: B/A/O accent, P pick, R reject, Alt+arrows move. */
function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || isTypingTarget(e.target)) return
  const digit = /^Digit([1-5])$/.exec(e.code)
  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) emit('move', e.key === 'ArrowUp' ? -1 : 1)
  else if (e.altKey) return
  else if (digit && e.shiftKey) emit('verdict', { accent_score: Number(digit[1]) === props.cand.verdict.accent_score ? null : Number(digit[1]) })
  else if (digit) emit('verdict', { fit: Number(digit[1]) })
  else if (e.shiftKey) return
  else if (ACCENT_KEYS[e.key.toLowerCase()]) emit('verdict', { accent: ACCENT_KEYS[e.key.toLowerCase()] })
  else if (e.key.toLowerCase() === 'p') emit('pick')
  else if (e.key.toLowerCase() === 'r') emit('reject')
  else return
  e.preventDefault()
}
</script>

<template>
  <div class="cand" :class="{ sel: picked, rej: rejected }" role="option" :aria-selected="picked" tabindex="0" :data-cand="id" @keydown="onKey">
    <div class="l1">
      <span class="grip" aria-hidden="true" title="Drag to rank">
        <svg width="10" height="16" viewBox="0 0 10 16"><circle cx="3" cy="3" r="1.3" fill="currentColor" /><circle cx="7" cy="3" r="1.3" fill="currentColor" /><circle cx="3" cy="8" r="1.3" fill="currentColor" /><circle cx="7" cy="8" r="1.3" fill="currentColor" /><circle cx="3" cy="13" r="1.3" fill="currentColor" /><circle cx="7" cy="13" r="1.3" fill="currentColor" /></svg>
      </span>
      <span class="rank num">{{ rank }}</span>
      <InlinePlay :id="cand.file" :title="`${speaker} · ${id}`" :subtitle="cand.file" />
      <span class="cid" :class="{ struck: rejected }">{{ id }}</span>
      <template v-if="sc">
        <ScoreChip :tone="sc.p_us > US_THRESHOLD ? 'hot' : 'ok'">p_us {{ sc.p_us.toFixed(2) }}</ScoreChip>
        <ScoreChip>{{ sc.top }} {{ sc.p_top.toFixed(2) }}</ScoreChip>
      </template>
      <ScoreChip v-else tone="none">unscored</ScoreChip>
      <Tag v-if="hasSeed">seed {{ cand.gen?.seed }}</Tag>
      <Flag v-else title="Seed was not recorded; this candidate cannot be regenerated, the WAV is the only copy">no seed</Flag>
      <label class="src"><input type="checkbox" :checked="isSource" @change="emit('source', ($event.target as HTMLInputElement).checked)" />Clone from</label>
      <span class="acts">
        <Btn icon size="sm" variant="ghost" :label="`Move ${id} up`" :disabled="first" @click="emit('move', -1)"><Icon name="up" :size="14" /></Btn>
        <Btn icon size="sm" variant="ghost" :label="`Move ${id} down`" :disabled="last" @click="emit('move', 1)"><Icon name="up" :size="14" class="flip" /></Btn>
        <Btn size="sm" variant="ghost" @click="emit('reject')">{{ rejected ? 'Undo reject' : 'Reject' }}</Btn>
        <Btn size="sm" :variant="picked ? 'primary' : 'default'" :pressed="picked" :disabled="rejected && !picked" @click="emit('pick')">{{ picked ? 'Picked' : 'Pick' }}</Btn>
      </span>
    </div>
    <div class="l2">
      <span class="lbl-s">Accent</span>
      <Seg :model-value="cand.verdict.accent ?? ''" :options="ACCENTS" :aria-label="`Accent of ${id}`" accent @update:model-value="emit('verdict', { accent: $event as 'british' | 'american' | 'other' })" />
      <StarScore :model-value="cand.verdict.accent_score ?? 0" label="Accent score" @update:model-value="emit('verdict', { accent_score: $event || null })" />
      <span class="lbl-s">Fit</span>
      <StarScore :model-value="cand.verdict.fit ?? 0" label="Fit" @update:model-value="$event && emit('verdict', { fit: $event })" />
      <template v-if="clones.length">
        <span class="lbl-s">Clone tests</span>
        <ClonePill v-for="k in clones" :key="k.file" :file="k.file" :text="testLabel(k)" :title="`${speaker} · ${id} · clone test`" :p-us="k.scores?.p_us" />
      </template>
      <Btn v-else size="sm" variant="ghost" :disabled="!canRenderTests" :title="canRenderTests ? undefined : 'Rendering clone tests from here needs a server route that is not available yet (tools/voice_design/clone_test.py makes them offline)'">Render 2 clone tests</Btn>
    </div>
  </div>
</template>

<style scoped>
.cand { display: flex; flex-direction: column; gap: 6px; padding: 8px 10px; border-radius: var(--r-md); border: 1px solid transparent; border-top-color: var(--line); }
.cand:focus-visible { outline-offset: -2px; }
.sel { background: var(--selected); border-color: var(--selected-line); }
.rej { opacity: 0.55; }
.l1, .l2 { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.l2 { padding-left: 78px; }
.grip { color: var(--text-3); cursor: grab; display: inline-flex; }
.rank { font-size: var(--fs-sm); color: var(--text-3); width: 16px; text-align: right; }
.cid { font: 500 14px var(--font-mono); color: var(--text); min-width: 28px; }
.struck { text-decoration: line-through; }
.lbl-s { font-size: var(--fs-xs); color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; }
.src { display: inline-flex; align-items: center; gap: 6px; font-size: var(--fs-sm); color: var(--text-3); cursor: pointer; }
.src input { accent-color: var(--accent); }
.acts { margin-left: auto; display: flex; gap: var(--s-1); align-items: center; }
.flip { transform: rotate(180deg); }
@media (max-width: 640px) { .l2 { padding-left: 0; } }
</style>
