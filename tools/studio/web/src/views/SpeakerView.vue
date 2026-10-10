<script setup lang="ts">
import { onMounted, watch } from 'vue'
import FxPanel from '../components/fx/FxPanel.vue'
import LinePanel from '../components/lines/LinePanel.vue'
import OptionsPanel from '../components/options/OptionsPanel.vue'
import ProfileBar from '../components/profile/ProfileBar.vue'
import ResultsPanel from '../components/results/ResultsPanel.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import SourcePanel from '../components/source/SourcePanel.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useJobWatch } from '../composables/useGeneration'
import { provideSpeakerContext } from '../composables/useSpeakerContext'
import { useSpeakerState } from '../composables/useSpeakerState'
import { useShortcuts } from '../composables/useShortcuts'
import { provideWorkbenchActions } from '../composables/useWorkbenchActions'
import { useWorkbenchKeys } from '../composables/useWorkbenchKeys'
import { useNavCountsStore } from '../stores/navCounts'
import { useSpeakersStore } from '../stores/speakers'

const props = defineProps<{ slug: string }>()
const ctx = useSpeakerState(props.slug)
provideSpeakerContext(ctx)
useWorkbenchKeys(provideWorkbenchActions())
useJobWatch(ctx)
const speakers = useSpeakersStore()
const navCounts = useNavCountsStore()

useShortcuts({
  title: 'Speaker workbench',
  groups: [
    { title: 'Speaker', items: [
      { label: 'Previous / next speaker', keys: ['[', ']'] },
      { label: 'Save profile', keys: ['S'] },
      { label: 'Register the pick', keys: ['P'] },
      { label: 'Edit the description', keys: ['E'] },
    ] },
    { title: 'Candidates', items: [
      { label: 'Switch candidate in Compare', keys: ['1', '–', '6'] },
      { label: 'Move the focused candidate', keys: ['Alt', '↑', '↓'] },
      { label: 'Accent British / American / Other', keys: ['B', 'A', 'O'] },
      { label: 'Fit 1–5', keys: ['1', '–', '5'] },
      { label: 'Accent score 1–5', keys: ['Shift', '1', '–', '5'] },
      { label: 'Pick / reject the focused candidate', keys: ['P', 'R'] },
    ] },
    { title: 'Generating', items: [
      { label: 'Live design take', keys: ['G'] },
      { label: 'Generate takes', keys: ['Ctrl', 'Enter'] },
      { label: 'Rate the focused take', keys: ['1', '–', '5'] },
    ] },
  ],
})

onMounted(ctx.load)
// keep the list's pick marker and the nav counts in step with picks made here
watch(() => ctx.detail.value?.design?.pick, (pick, before) => {
  if (pick === undefined) return
  speakers.setPick(props.slug, !!pick)
  if (before !== undefined && !!pick !== !!before) void navCounts.load()
})
</script>

<template>
  <div class="workbench">
    <ProfileBar :slug="slug" />
    <main class="page">
      <EmptyState v-if="ctx.error.value" state="error" title="This speaker did not load" :message="ctx.error.value" />
      <Skeleton v-else-if="!ctx.detail.value" :rows="6" />
      <div v-else class="split">
        <div class="main">
          <SourcePanel />
          <LinePanel />
          <OptionsPanel />
          <FxPanel />
        </div>
        <aside class="side sticky results" aria-label="Results"><ResultsPanel /></aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.workbench { display: flex; flex-direction: column; }
.page { padding-left: var(--s-5); padding-right: var(--s-5); }
.side { flex-basis: 380px; }
.results { max-height: calc(100vh - var(--topbar-h) - var(--bar-h) - var(--s-6) - 56px); overflow-y: auto; }
@media (max-width: 960px) {
  .results { position: static; max-height: none; overflow: visible; }
}
@media (max-width: 640px) { .page { padding-left: var(--s-3); padding-right: var(--s-3); } }
</style>
