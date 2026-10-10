<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Candidate, CloneTest } from '../../api/types'
import { useGlobalAudio } from '../../composables/globalAudio'
import { shortId } from '../../composables/useDesign'
import { blurAfterPointer, isTypingTarget } from '../../utils/keys'
import { formatPlayhead } from '../../utils/time'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import Kbd from '../ui/Kbd.vue'
import SeekTrack from '../ui/SeekTrack.vue'
import Seg from '../ui/Seg.vue'

const MAX_SLOTS = 6
const MAX_TESTS = 2
const DESIGN = 'design'
const props = defineProps<{ candidates: Candidate[]; clones: CloneTest[]; speaker: string }>()

const audio = useGlobalAudio()
const lineKey = ref(DESIGN)
const currentId = ref<string | null>(null)

const slots = computed(() => props.candidates.slice(0, MAX_SLOTS))
const tests = computed(() => [...new Set(props.clones.map((c) => c.text))].slice(0, MAX_TESTS))
const lineOptions = computed(() => [
  { value: DESIGN, label: 'Design sample' },
  ...tests.value.map((t, i) => ({ value: `t${i}`, label: `Test ${i + 1}: ${t.split(/\s+/).slice(0, 1).join(' ')}` })),
])
const lineName = computed(() => lineOptions.value.find((o) => o.value === lineKey.value)?.label ?? 'Design sample')

function pathFor(c: Candidate): string | null {
  if (lineKey.value === DESIGN) return c.file
  const text = tests.value[Number(lineKey.value.slice(1))]
  return props.clones.find((k) => k.candidate === c.id && k.text === text)?.file ?? null
}
const meta = (c: Candidate) => ({ title: `${props.speaker} · ${shortId(c.id)} · ${lineName.value.toLowerCase()}`, subtitle: pathFor(c) ?? '' })
const current = computed(() => slots.value.find((c) => c.id === currentId.value) ?? null)
const currentPath = computed(() => (current.value ? pathFor(current.value) : null))
const owns = computed(() => slots.value.some((c) => pathFor(c) !== null && pathFor(c) === audio.state.id))
const active = computed(() => !!currentPath.value && audio.state.id === currentPath.value)
const playingNow = computed(() => active.value && audio.state.isPlaying)

/** Listen to candidate `c`; if a clip of this bar is already loaded the playhead carries over. */
function choose(c: Candidate) {
  currentId.value = c.id
  const path = pathFor(c)
  if (!path) return
  if (owns.value && audio.state.id !== path) audio.switchTo(path, undefined, meta(c), 'fraction')
  else if (!owns.value) audio.play(path, undefined, meta(c))
}
function togglePlay(e: MouseEvent) {
  blurAfterPointer(e)
  const c = current.value ?? slots.value[0]
  if (!c) return
  currentId.value = c.id
  const path = pathFor(c)
  if (path) audio.play(path, undefined, meta(c))
}
watch(lineKey, () => {
  const c = current.value
  if (c && owns.value && pathFor(c)) audio.switchTo(pathFor(c) as string, undefined, meta(c), 'fraction')
})
watch(slots, (s) => { if (currentId.value && !s.some((c) => c.id === currentId.value)) currentId.value = null })

function step(delta: number) {
  const i = slots.value.findIndex((c) => c.id === currentId.value)
  const next = slots.value[Math.min(Math.max((i < 0 ? 0 : i + delta), 0), slots.value.length - 1)]
  if (next) choose(next)
}
const transport = { prev: () => step(-1), next: () => step(1) }
function onKey(e: KeyboardEvent) {
  if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || isTypingTarget(e.target)) return
  const n = Number(e.key)
  if (!Number.isInteger(n) || n < 1 || n > slots.value.length) return
  e.preventDefault()
  choose(slots.value[n - 1])
}
onMounted(() => {
  document.addEventListener('keydown', onKey)
  audio.setTransport(transport)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  audio.clearTransport(transport)
})
const seek = (f: number) => active.value && audio.seek(f * audio.state.duration)
const top = (c: Candidate) => (c.scores ? `${c.scores.top} ${c.scores.p_top.toFixed(2)}` : 'unscored')
</script>

<template>
  <div v-if="slots.length" class="ab" aria-label="Compare candidates">
    <div class="head">
      <b class="ttl">Compare on</b>
      <Seg v-model="lineKey" :options="lineOptions" aria-label="Compare line" />
      <span class="hint">Keys <Kbd>1</Kbd>–<Kbd>{{ slots.length }}</Kbd> switch, playhead kept</span>
    </div>
    <div class="slots" role="group" aria-label="Candidates">
      <button v-for="(c, n) in slots" :key="c.id" type="button" class="slot" :aria-pressed="c.id === currentId" :disabled="!pathFor(c)" :title="pathFor(c) ? undefined : 'No clone test of this candidate on this line'" @click="choose(c)">
        <Kbd>{{ n + 1 }}</Kbd>
        <span class="lbl"><b>{{ shortId(c.id) }}</b><span>{{ pathFor(c) ? top(c) : 'no clip' }}</span></span>
      </button>
    </div>
    <div class="track-row">
      <button type="button" class="play" :class="{ on: playingNow }" :disabled="!slots.length" :aria-label="playingNow ? 'Pause' : 'Play'" @click="togglePlay"><Icon :name="playingNow ? 'pause' : 'play'" :size="12" /></button>
      <span class="num muted time">{{ formatPlayhead(active ? audio.state.current : 0) }}</span>
      <SeekTrack :model-value="active ? audio.progress.value : 0" label="Seek" :disabled="!active" @update:model-value="seek" />
      <span class="num muted time">{{ formatPlayhead(active ? audio.state.duration : 0) }}</span>
      <Btn size="sm" variant="ghost" :pressed="audio.state.loop" kbd="L" @click="audio.setLoop(!audio.state.loop)">Loop</Btn>
    </div>
  </div>
</template>

<style scoped>
.ab { display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-3); border-radius: var(--r-lg); background: var(--n-1); border: 1px solid var(--line-strong); }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); font-size: var(--fs-sm); color: var(--text-3); }
.ttl { color: var(--text); }
.hint { margin-left: auto; }
.slots { display: flex; flex-wrap: wrap; gap: var(--s-2); }
.slot { flex: 1 1 96px; display: flex; align-items: center; gap: var(--s-2); min-height: var(--hit-lg); padding: 6px 10px; border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text-2); cursor: pointer; text-align: left; min-width: 0; }
.slot:hover { border-color: var(--n-6); color: var(--text); }
.slot[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-tint); color: var(--text); }
.slot:disabled { opacity: 0.55; cursor: not-allowed; border-style: dashed; }
.lbl { display: flex; flex-direction: column; min-width: 0; line-height: 1.2; }
.lbl b { font: 600 13px var(--font-mono); }
.lbl span { font: var(--fs-xs) var(--font-mono); color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.track-row { display: flex; align-items: center; gap: var(--s-2); }
.time { font-size: var(--fs-sm); }
.play { width: var(--hit); height: var(--hit); flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); cursor: pointer; padding: 0; }
.play:hover { border-color: var(--accent); color: var(--accent-hi); }
.play.on { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
@media (max-width: 640px) { .hint { margin-left: 0; } .slot { flex-basis: 30%; } }
</style>
