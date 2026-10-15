<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import LabelEditor from '../components/voices/LabelEditor.vue'
import LabelFilter from '../components/voices/LabelFilter.vue'
import VoiceQueue from '../components/voices/VoiceQueue.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import Btn from '../components/ui/Btn.vue'
import InlineError from '../components/ui/InlineError.vue'
import InlinePlay from '../components/ui/InlinePlay.vue'
import SearchField from '../components/ui/SearchField.vue'
import Seg from '../components/ui/Seg.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useVoiceLabeling, type LabelingView } from '../composables/useVoiceLabeling'
import type { VoiceSort } from '../utils/castVoices'
import { fileUrl } from '../utils/fileUrl'
import { isTypingTarget } from '../utils/keys'

const L = useVoiceLabeling()
const { store } = L
onMounted(() => { if (!store.voices.length) store.load(); document.addEventListener('keydown', onKey) })
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

const VIEWS = [{ value: 'todo' as LabelingView, label: 'To label' }, { value: 'done' as LabelingView, label: 'Done' }, { value: 'all' as LabelingView, label: 'All' }]
const SORTS = [{ value: 'lines' as VoiceSort, label: 'Most lines' }, { value: 'name' as VoiceSort, label: 'A to Z' }]
const firstLoad = computed(() => store.loading && !store.voices.length)
const pct = computed(() => (store.progress ? Math.round((100 * store.progress.complete) / Math.max(1, store.progress.total)) : 0))

function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return
  if (e.key === 'ArrowDown' || e.key === 'j') { e.preventDefault(); L.move(1) }
  else if (e.key === 'ArrowUp' || e.key === 'k') { e.preventDefault(); L.move(-1) }
}
</script>

<template>
  <div class="page voices">
    <div class="page-head">
      <div class="titles">
        <h1 class="page-title">BG3 Voices</h1>
        <span class="page-sub">Label each BG3 voice once (gender, age, class, processing, pitch, and anything extra). Then the Casting page can filter to, say, a low-class young woman with a high voice.</span>
      </div>
      <div v-if="store.progress" class="progress">
        <b>{{ store.progress.complete }}</b> of {{ store.progress.total }} fully labelled ({{ pct }}%)
        <div class="bar" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100"><div class="fill" :style="{ width: pct + '%' }" /></div>
      </div>
    </div>

    <InlineError v-if="store.error" title="Labelling problem"> {{ store.error }} <Btn size="sm" @click="store.load()">Retry</Btn></InlineError>
    <Skeleton v-if="firstLoad" :rows="6" />
    <div v-else-if="store.voices.length" class="split">
      <div class="side">
        <div class="filters">
          <Seg v-model="L.view.value" :options="VIEWS" aria-label="Which voices to show" />
          <SearchField v-model="L.query.value" placeholder="Find a voice" label="Find a voice" />
          <Seg v-model="L.sort.value" :options="SORTS" aria-label="Sort voices" />
          <LabelFilter v-model="L.filters.value" :schema="store.schema" />
        </div>
        <EmptyState v-if="!L.rows.value.length" :message="L.view.value === 'todo' ? 'Everything here is labelled.' : 'No voices for these filters.'" />
        <VoiceQueue v-else :rows="L.rows.value" :selected="L.current.value?.slug ?? null" :schema="store.schema" @select="L.select" />
      </div>
      <div v-if="L.current.value" class="main">
        <section class="card">
          <header class="head">
            <h2 class="name">{{ L.current.value.name }}</h2>
            <span class="meta">{{ L.current.value.lines.toLocaleString() }} lines · {{ L.current.value.minutes }} min<template v-if="L.current.value.f0"> · {{ Math.round(L.current.value.f0) }} Hz</template>
              <template v-if="L.current.value.aliases?.length"> · also {{ L.current.value.aliases.join(', ') }}</template></span>
            <span v-if="L.current.value.used_by.length" class="cast">cast as {{ L.current.value.used_by.join(', ') }}</span>
          </header>
          <ul class="refs">
            <li v-for="(r, i) in L.current.value.refs" :key="r.wav">
              <InlinePlay :id="r.wav" :src="fileUrl(r.wav)" :title="L.current.value.name" :subtitle="`clip ${i + 1}`" />
              <span class="rt">{{ r.text }}</span>
            </li>
          </ul>
          <LabelEditor :voice="L.current.value" :schema="store.schema" @set="L.label" />
          <footer class="foot">
            <Btn size="sm" @click="L.move(-1)">Previous</Btn>
            <Btn size="sm" @click="L.move(1)">Next</Btn>
            <Btn size="sm" variant="primary" @click="L.nextIncomplete()">Next to label</Btn>
            <label class="opt"><input v-model="L.autoAdvance.value" type="checkbox" /> Move on when all five are set</label>
            <label class="opt"><input v-model="L.autoplay.value" type="checkbox" /> Play on select</label>
            <span class="hint">Up / Down or J / K to move</span>
          </footer>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.titles { display: flex; flex-direction: column; gap: var(--s-1); flex: 1 1 360px; min-width: 0; }
.progress { margin-left: auto; min-width: 240px; color: var(--text-2); display: flex; flex-direction: column; gap: 4px; }
.bar { height: 6px; background: var(--inset); border-radius: 3px; overflow: hidden; }
.fill { height: 100%; background: var(--accent); }
.filters { display: flex; flex-direction: column; gap: var(--s-2); }
.side { max-width: 420px; }
.card { display: flex; flex-direction: column; gap: var(--s-4); padding: var(--s-4); background: var(--raised); border: 1px solid var(--line); border-radius: var(--r-lg); }
.head { display: flex; flex-direction: column; gap: 2px; }
.name { margin: 0; font-family: var(--font-display); font-size: var(--fs-xl); letter-spacing: 0.03em; }
.meta { color: var(--text-3); font-family: var(--font-mono); font-size: var(--fs-xs); }
.cast { color: var(--good); font-size: var(--fs-sm); }
.refs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--s-2); }
.refs li { display: flex; align-items: center; gap: var(--s-3); }
.rt { color: var(--text-2); font-size: var(--fs-sm); min-width: 0; }
.foot { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3); padding-top: var(--s-2); border-top: 1px solid var(--line); }
.opt { display: inline-flex; align-items: center; gap: 6px; color: var(--text-2); font-size: var(--fs-sm); }
.hint { color: var(--text-3); font-size: var(--fs-xs); margin-left: auto; }
@media (max-width: 480px) { .progress { margin-left: 0; } .side { max-width: none; flex-basis: 100%; } }
</style>
