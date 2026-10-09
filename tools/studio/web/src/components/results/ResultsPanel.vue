<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { api } from '../../api/client'
import type { Take } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useModelStore } from '../../stores/model'
import { runBatch } from '../../utils/batch'
import EmptyState from '../shared/EmptyState.vue'
import TakeRow from './TakeRow.vue'

const ctx = useSpeakerContext()
const model = useModelStore()
const running = ref(false)
const stopRequested = ref(false)
const progress = ref('')
const error = ref('')
const GROUP_PAGE = 50
const shown = ref(GROUP_PAGE)
// The page is rebuilt on every route change; a batch left running would keep using the model with no Stop button.
onBeforeUnmount(() => { stopRequested.value = true })

const chosenLines = computed(() => ctx.lines.value.filter((l) => ctx.selectedLines.value.has(l.guid)))
const total = computed(() => chosenLines.value.length * ctx.chosenSources.value.length)
const hint = computed(() => (total.value ? '' : 'Tick a source and some lines first.'))

const groups = computed(() => {
  const by = new Map<string, Take[]>()
  for (const t of ctx.takes.value) by.set(t.guid ?? t.text, [...(by.get(t.guid ?? t.text) ?? []), t])
  return [...by.entries()].map(([key, takes]) => ({ key, takes, line: ctx.lines.value.find((l) => l.guid === key) ?? null }))
})

const visibleGroups = computed(() => groups.value.slice(0, shown.value))

async function generate() {
  running.value = true
  stopRequested.value = false
  error.value = ''
  let i = 0
  const res = await runBatch({
    lines: chosenLines.value,
    sources: ctx.chosenSources.value,
    options: ctx.options.value,
    shouldStop: () => stopRequested.value,
    generate: (req) => {
      progress.value = `generating ${++i} / ${total.value}…`
      return api.cloneGenerate(ctx.slug, req)
    },
    onTake: async (t) => {
      ctx.upsertTake(t)
      if (ctx.fxChosen.value.length) {
        try {
          ctx.upsertTake(await api.takeFx(ctx.slug, t.id, ctx.fxChosen.value))
        } catch (e) {
          error.value = e instanceof Error ? e.message : String(e)
        }
      }
    },
  })
  progress.value = `done, ${res.done} takes`
  if (res.error) error.value = res.error
  running.value = false
}
</script>

<template>
  <div>
    <div class="bar">
      <button data-generate class="primary" :disabled="!model.ready || running || !total" :title="model.reason || hint" @click="generate">
        Generate {{ total }} take{{ total === 1 ? '' : 's' }}
      </button>
      <button v-if="running" @click="stopRequested = true">Stop</button>
      <span class="dim">{{ progress }}</span>
      <span v-if="!model.ready" class="dim">{{ model.reason }}</span>
      <span v-else-if="hint" class="dim">{{ hint }}</span>
    </div>
    <p v-if="error" class="err">{{ error }}</p>
    <EmptyState v-if="!groups.length" message="No takes yet. Tick a source and some lines, then Generate." />
    <div v-for="g in visibleGroups" :key="g.key" class="group">
      <div class="text">{{ g.takes[0].text }}</div>
      <TakeRow v-for="t in g.takes" :key="t.id" :take="t" :line="g.line" />
    </div>
    <button v-if="groups.length > shown" data-more @click="shown += GROUP_PAGE">Show {{ Math.min(GROUP_PAGE, groups.length - shown) }} more of {{ groups.length - shown }}</button>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
.primary { background: var(--acc); color: #0b1220; border-color: var(--acc); }
.group { border-top: 1px solid var(--line); padding: 8px 0; }
.text { margin-bottom: 4px; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); font-size: 13px; }
</style>
