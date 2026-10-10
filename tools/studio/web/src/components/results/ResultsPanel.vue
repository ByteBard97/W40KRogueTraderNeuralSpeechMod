<script setup lang="ts">
import { computed, ref } from 'vue'
import type { JobView } from '../../api/jobs'
import type { Take } from '../../api/types'
import { useCloneGeneration } from '../../composables/useGeneration'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useWorkbenchAction } from '../../composables/useWorkbenchActions'
import SectionCard from '../shared/SectionCard.vue'
import EmptyState from '../shared/EmptyState.vue'
import BusyJobCard from '../ui/BusyJobCard.vue'
import Btn from '../ui/Btn.vue'
import InlineError from '../ui/InlineError.vue'
import Tag from '../ui/Tag.vue'
import TakeRow from './TakeRow.vue'

const GROUP_PAGE = 20
const TEXT_CHARS = 110
const MAX_NAMED = 2
const MAX_FILL = 0.95

const ctx = useSpeakerContext()
const gen = useCloneGeneration()
const shown = ref(GROUP_PAGE)

const groups = computed(() => {
  const by = new Map<string, Take[]>()
  for (const t of ctx.takes.value) by.set(t.guid ?? t.text, [...(by.get(t.guid ?? t.text) ?? []), t])
  return [...by.entries()].map(([key, takes]) => ({ key, takes, line: ctx.lines.value.find((l) => l.guid === key) ?? null }))
})
const visibleGroups = computed(() => groups.value.slice(0, shown.value))

const sourceName = (key: string) => key.replace(/^(real|cand|sup):/, '').replace(/\.wav$/, '').split('/').pop() ?? key
const summary = computed(() => {
  const names = ctx.chosenSources.value.map((s) => sourceName(s.key))
  const src = !names.length ? 'no source' : names.length <= MAX_NAMED ? names.join(', ') : `${names.slice(0, MAX_NAMED).join(', ')} +${names.length - MAX_NAMED}`
  const n = ctx.selectedLines.value.size
  return `source ${src} · ${n} line${n === 1 ? '' : 's'} · ${ctx.fxChosen.value.length} FX`
})
const hint = computed(() => {
  const est = gen.estimateS.value ? `~${gen.estimateS.value} s on the current model · ` : ''
  return `${est}runs in the background; keep ranking`
})

const trim = (t: string | null) => (t && t.length > TEXT_CHARS ? `${t.slice(0, TEXT_CHARS)}…` : (t ?? ''))
const elapsed = (j: JobView) => j.current?.elapsed_s ?? 0
function fill(j: JobView): number | undefined {
  const exp = j.current?.expected_s ?? j.expected_s
  return j.state === 'running' && exp ? Math.min(elapsed(j) / exp, MAX_FILL) : undefined
}
const cardTitle = (j: JobView) => (j.state === 'running' ? `Take ${j.index} of ${j.total} · ${trim(j.current?.text ?? null)}` : `Queued · ${j.total} take${j.total === 1 ? '' : 's'}`)
const queued = (j: JobView) => Math.max(j.total - j.done - (j.state === 'running' ? 1 : 0), 0)

useWorkbenchAction('generate-takes', () => void gen.generate())
</script>

<template>
  <SectionCard title="Results" step="5" :summary="summary">
    <div class="body">
      <Btn variant="primary" size="lg" class="wide" data-generate :disabled="!!gen.blocked.value || gen.syncRunning.value" :title="gen.blocked.value" kbd="⌘↵" @click="gen.generate()">
        Generate {{ gen.total.value }} take{{ gen.total.value === 1 ? '' : 's' }}
      </Btn>
      <div class="muted small">{{ gen.blocked.value || hint }}</div>
      <div v-if="gen.syncRunning.value || gen.syncStatus.value" class="muted small" role="status">{{ gen.syncStatus.value }} <Btn v-if="gen.syncRunning.value" size="sm" variant="ghost" @click="gen.cancelAll()">Stop</Btn></div>
      <InlineError v-if="gen.problem.value" title="The last batch had a problem. "><span>{{ gen.problem.value }}</span></InlineError>

      <BusyJobCard v-for="j in gen.activeJobs.value" :key="j.id" :title="cardTitle(j)" :elapsed-s="elapsed(j)" :progress="fill(j)" :detail="queued(j) ? `${queued(j)} more queued · finishes the current take` : 'finishes the current take if cancelled'" cancelable @cancel="gen.cancel(j.id)" />
      <Btn v-if="gen.activeJobs.value.length > 1" size="sm" variant="ghost" data-cancel-all @click="gen.cancelAll()">Cancel all</Btn>

      <EmptyState v-if="!groups.length && !gen.running.value" message="No takes yet. Tick a source and some lines, then Generate." />
      <div v-for="g in visibleGroups" :key="g.key" class="res">
        <div class="head">
          <Tag v-if="g.line">{{ g.line.emotion ?? '—' }}{{ g.line.intensity !== null && g.line.intensity !== undefined ? ` ${g.line.intensity}` : '' }}</Tag>
          <span class="text">{{ trim(g.takes[0].text) }}</span>
        </div>
        <TakeRow v-for="t in g.takes" :key="t.id" :take="t" :line="g.line" />
      </div>
      <Btn v-if="groups.length > shown" size="sm" data-more @click="shown += GROUP_PAGE">Show {{ Math.min(GROUP_PAGE, groups.length - shown) }} more of {{ groups.length - shown }}</Btn>
    </div>
  </SectionCard>
</template>

<style scoped>
.body { display: flex; flex-direction: column; gap: 6px; }
.wide { width: 100%; }
.small { font-size: var(--fs-sm); }
.res { display: flex; flex-direction: column; gap: 4px; padding: 10px 0; border-top: 1px solid var(--line); }
.head { display: flex; gap: var(--s-2); align-items: baseline; }
.text { font-size: 13px; overflow-wrap: anywhere; }
</style>
