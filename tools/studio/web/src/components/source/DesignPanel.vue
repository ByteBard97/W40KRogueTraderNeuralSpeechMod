<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useDesign } from '../../composables/useDesign'
import { useDesignGeneration } from '../../composables/useGeneration'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useWorkbenchAction } from '../../composables/useWorkbenchActions'
import Btn from '../ui/Btn.vue'
import CandidateRanker from './CandidateRanker.vue'
import CompareBar from './CompareBar.vue'
import DesignJobRow from './DesignJobRow.vue'
import LiveDesign from './LiveDesign.vue'

const ctx = useSpeakerContext()
const d = useDesign()
const gen = useDesignGeneration()

const description = ref(d.design.value?.description ?? '')
const editing = ref(false)
const box = ref<HTMLTextAreaElement | null>(null)
// the detail is replaced after Keep, verdicts and reorders; keep the box in step with what is saved
watch(() => d.design.value?.description, (t) => { if (t !== undefined && !editing.value) description.value = t })

async function edit() {
  editing.value = true
  await nextTick()
  box.value?.focus()
}
function done(save: boolean) {
  editing.value = false
  if (save) void d.saveDescription(description.value)
  else description.value = d.design.value?.description ?? ''
}
useWorkbenchAction('edit-description', edit)

const sourceIds = computed(() => new Set([...ctx.selectedSources.value].filter((k) => k.startsWith('cand:')).map((k) => k.slice('cand:'.length))))
function tick(id: string, on: boolean) {
  const next = new Set(ctx.selectedSources.value)
  if (on) next.add(`cand:${id}`)
  else next.delete(`cand:${id}`)
  ctx.selectedSources.value = next
}
const speaker = computed(() => ctx.detail.value?.summary.name ?? '')
</script>

<template>
  <div v-if="d.design.value" class="design">
    <div class="desc">
      <div class="flex">
        <div class="lbl-s">Description</div>
        <p v-if="!editing" class="text">{{ description }}</p>
        <textarea v-else ref="box" v-model="description" class="field" rows="3" aria-label="Voice description" @blur="done(true)" @keydown.esc.prevent="done(false)" />
      </div>
      <Btn v-if="!editing" size="sm" variant="ghost" kbd="E" @click="edit">Edit</Btn>
    </div>

    <CompareBar :candidates="d.candidates.value" :clones="d.design.value.clones" :speaker="speaker" />

    <div>
      <div class="rank-head"><b>Ranking</b><span class="muted">Drag the handle or Alt+↑↓ · B / A / O accent · Shift+1–5 accent score · 1–5 fit · P pick · R reject</span></div>
      <CandidateRanker
        :candidates="d.candidates.value"
        :source-ids="sourceIds"
        :pick-id="d.pickId.value"
        :clones="d.design.value.clones"
        :speaker="speaker"
        @reorder="d.reorder"
        @verdict="(id, patch) => d.setVerdict(id, patch)"
        @pick="d.togglePick"
        @reject="d.toggleReject"
        @source="tick"
      />
      <DesignJobRow v-for="(j, n) in gen.activeJobs.value" :key="j.id" :job="j" :next-id="`c${Number(d.nextId.value.slice(1)) + n}`" @cancel="gen.cancel(j.id)" />
    </div>

    <LiveDesign :description="description" />
  </div>
</template>

<style scoped>
.design { display: flex; flex-direction: column; gap: var(--s-4); }
.desc { display: flex; flex-wrap: wrap; gap: var(--s-3); align-items: flex-start; }
.flex { flex: 1 1 400px; min-width: 0; }
.lbl-s { font-size: var(--fs-xs); color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: var(--s-1); }
.text { margin: 0; font-size: 15px; line-height: 1.5; }
.rank-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s-2); padding: 0 var(--s-1) 6px; font-size: 14px; }
.rank-head .muted { font-size: var(--fs-sm); }
</style>
