<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import QaFilters from '../components/qa/QaFilters.vue'
import QaRow from '../components/qa/QaRow.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { useAudioPlayer } from '../composables/useAudioPlayer'
import { useQaKeys } from '../composables/useQaKeys'
import { useQaStore } from '../stores/qa'
import type { QaFilter, QaFx, QaVerdictValue } from '../api/types'
import { fxUrl } from '../utils/fileUrl'
import type { QaAction } from '../utils/qaKeys'

const FX_CHOICES: QaFx[] = ['mild', 'strong']
const qa = useQaStore()
const { play } = useAudioPlayer()
const sel = ref(0)
const FX_KEY = 'studio.qa.fx'
function savedFx(): QaFx | '' {
  try {
    const v = localStorage.getItem(FX_KEY)
    return FX_CHOICES.includes(v as QaFx) ? (v as QaFx) : ''
  } catch { return '' }
}
const fx = ref<QaFx | ''>(savedFx())
let lastFx: QaFx = fx.value || 'mild'
watch(fx, (v) => {
  if (v) lastFx = v
  try { localStorage.setItem(FX_KEY, v) } catch { /* private window: the choice just is not remembered */ }
})
const refTally = computed(() => Object.entries(qa.stats.by_ref ?? {}).map(([k, r]) => `${k}: ${r.good}g/${r.bad}b/${r.total}`).join('  '))

const current = computed(() => qa.items[sel.value])
const from = computed(() => (qa.total ? qa.offset + 1 : 0))
const to = computed(() => qa.offset + qa.items.length)

async function init() {
  await qa.loadRuns()
  await Promise.all([qa.loadFacets(), qa.loadPage(0)])
}
onMounted(init)

const reload = async (load: () => Promise<void>) => { sel.value = 0; await load() }
const pickRun = (id: string) => reload(() => qa.setRun(id))
const nextPage = () => reload(qa.nextPage)
const prevPage = () => reload(qa.prevPage)
const applyFilter = (f: QaFilter) => reload(() => qa.setFilter(f))

const move = (by: number) => { sel.value = Math.min(Math.max(sel.value + by, 0), Math.max(qa.items.length - 1, 0)) }
function nextUnjudged() {
  const i = qa.items.findIndex((c, k) => k > sel.value && !c.verdict)
  if (i >= 0) sel.value = i
}
function judge(v: QaVerdictValue | null) {
  const c = current.value
  if (!c) return
  void qa.setVerdict(c.guid, v)
  if (v) move(1)
}
function playCurrent() {
  const c = current.value
  if (!c) return
  if (fx.value) play(fxUrl(c.wav, fx.value), fxUrl(c.wav, fx.value))
  else play(c.wav)
}

const HANDLERS: Record<QaAction, () => void> = {
  next: () => move(1),
  prev: () => move(-1),
  play: playCurrent,
  good: () => judge('good'),
  bad: () => judge('bad'),
  clear: () => judge(null),
  nextUnjudged,
  toggleFx: () => { fx.value = fx.value ? '' : lastFx },
}
useQaKeys((a) => HANDLERS[a]())
</script>

<template>
  <div>
    <h1>Render QA</h1>
    <p class="dim">
      Listen to rendered clips, judge them good or bad, and compare against the clone reference, the earlier render and the game's own voice.
      Keys: j/k move, space plays, g good, b bad, u clear, n next unjudged, x compressor on or off. Verdicts save as you click.
    </p>
    <div class="bar">
      <select :value="qa.run" data-run @change="pickRun(($event.target as HTMLSelectElement).value)">
        <option v-for="r in qa.runs" :key="r.id" :value="r.id">{{ r.label }} ({{ r.clips }})</option>
      </select>
      <label class="dim">compressor
        <select v-model="fx" data-fx>
          <option value="">off</option>
          <option v-for="f in FX_CHOICES" :key="f" :value="f">{{ f }}</option>
        </select>
      </label>
    </div>
    <QaFilters :facets="qa.facets" :filter="qa.filter" @change="applyFilter" />
    <p class="dim" data-stats>
      {{ qa.stats.good }} good · {{ qa.stats.bad }} bad · {{ qa.stats.unjudged }} unjudged · showing {{ from }}-{{ to }} of {{ qa.total }}<template v-if="refTally"> · <span data-ref-tally>{{ refTally }}</span></template>
    </p>
    <p v-if="qa.error" class="err">{{ qa.error }}</p>
    <EmptyState v-if="!qa.items.length && !qa.loading" message="No clips for these filters." />
    <QaRow
      v-for="(c, i) in qa.items"
      :key="c.guid"
      :clip="c"
      :selected="i === sel"
      :fx="fx || null"
      @select="sel = i"
      @verdict="qa.setVerdict(c.guid, $event)"
      @tags="qa.setDetails(c.guid, $event, c.verdict?.note ?? '')"
      @note="qa.setDetails(c.guid, c.verdict?.tags ?? [], $event)"
    />
    <div class="pager">
      <button data-prev :disabled="!qa.canPrev || qa.loading" @click="prevPage">Previous</button>
      <button data-next :disabled="!qa.hasNext || qa.loading" @click="nextPage">Next</button>
    </div>
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); }
.bar { display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }
.pager { display: flex; gap: 8px; margin: 10px 0; }
</style>
