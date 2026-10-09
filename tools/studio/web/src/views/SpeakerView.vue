<script setup lang="ts">
import { onMounted } from 'vue'
import EmptyState from '../components/shared/EmptyState.vue'
import ProfileBar from '../components/profile/ProfileBar.vue'
import SourcePanel from '../components/source/SourcePanel.vue'
import SectionCard from '../components/shared/SectionCard.vue'
import LinePanel from '../components/lines/LinePanel.vue'
import OptionsPanel from '../components/options/OptionsPanel.vue'
import FxPanel from '../components/fx/FxPanel.vue'
import ResultsPanel from '../components/results/ResultsPanel.vue'
import { provideSpeakerContext } from '../composables/useSpeakerContext'
import { useSpeakerState } from '../composables/useSpeakerState'

const props = defineProps<{ slug: string }>()
const ctx = useSpeakerState(props.slug)
provideSpeakerContext(ctx)
onMounted(ctx.load)
</script>

<template>
  <div>
    <p v-if="ctx.error.value" class="err">{{ ctx.error.value }}</p>
    <EmptyState v-else-if="!ctx.detail.value" message="Loading…" />
    <template v-else>
      <h1>{{ ctx.detail.value.summary.name }} <span class="dim">{{ ctx.detail.value.summary.origin }} voice</span></h1>
      <ProfileBar />
      <SourcePanel />
      <SectionCard title="2. Test lines"><LinePanel /></SectionCard>
      <SectionCard title="3. Model options"><OptionsPanel /></SectionCard>
      <SectionCard title="4. Post-processing"><FxPanel /></SectionCard>
      <SectionCard title="5. Results"><ResultsPanel /></SectionCard>
    </template>
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.dim { color: var(--dim); font-size: 13px; }
.err { color: var(--bad); }
</style>
