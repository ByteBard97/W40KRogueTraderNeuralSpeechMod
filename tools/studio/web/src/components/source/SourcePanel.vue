<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDesign } from '../../composables/useDesign'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import SectionCard from '../shared/SectionCard.vue'
import Seg from '../ui/Seg.vue'
import DesignPanel from './DesignPanel.vue'
import RealClipList from './RealClipList.vue'
import SuppliedClip from './SuppliedClip.vue'

type Tab = 'designed' | 'catalogue' | 'supplied'

const ctx = useSpeakerContext()
const d = useDesign()
const detail = computed(() => ctx.detail.value)
const hasDesign = computed(() => !!detail.value?.design)
const hasClips = computed(() => !!detail.value && (detail.value.summary.origin === 'real' || detail.value.clips.length > 0))

const tabs = computed(() => [
  ...(hasDesign.value ? [{ value: 'designed' as const, label: 'Designed' }] : []),
  ...(hasClips.value ? [{ value: 'catalogue' as const, label: 'Catalogue clips' }] : []),
  { value: 'supplied' as const, label: 'Supplied wav' },
])
const chosen = ref<Tab | null>(null)
const tab = computed<Tab>({
  get: () => (chosen.value && tabs.value.some((t) => t.value === chosen.value) ? chosen.value : tabs.value[0].value),
  set: (v) => (chosen.value = v),
})

const title = computed(() => (hasDesign.value ? 'Source · designed voice' : 'Source · real voice'))
const summary = computed(() => {
  const ticked = ctx.chosenSources.value.length
  const tickedText = `${ticked} ticked as clone source${ticked === 1 ? '' : 's'}`
  if (tab.value === 'designed') {
    const n = d.candidates.value.length
    return `${n} candidate${n === 1 ? '' : 's'} · ${d.scoredCount.value} / ${n} scored · ${d.pickId.value ? `picked ${d.pickId.value.replace('.wav', '')}` : 'no pick yet'} · ${tickedText}`
  }
  if (tab.value === 'catalogue') return `${detail.value?.clips.length ?? 0} clips · ${tickedText}`
  return `${ctx.supplied.value.length} supplied · ${tickedText}`
})
</script>

<template>
  <SectionCard :title="title" step="1" :summary="summary">
    <template #actions><Seg v-if="tabs.length > 1" v-model="tab" :options="tabs" aria-label="Source type" /></template>
    <div class="body">
      <p class="muted hint">Tick the clips to clone from. Several ticked clips are compared on the same lines with the same seed.</p>
      <DesignPanel v-if="tab === 'designed'" />
      <RealClipList v-else-if="tab === 'catalogue' && detail" :clips="detail.clips" />
      <SuppliedClip v-else />
    </div>
  </SectionCard>
</template>

<style scoped>
.body { display: flex; flex-direction: column; gap: var(--s-3); }
.hint { margin: 0; font-size: var(--fs-sm); }
</style>
