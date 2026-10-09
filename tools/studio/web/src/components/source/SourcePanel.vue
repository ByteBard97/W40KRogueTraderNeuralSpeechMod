<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import SectionCard from '../shared/SectionCard.vue'
import DesignPanel from './DesignPanel.vue'
import RealClipList from './RealClipList.vue'
import SuppliedClip from './SuppliedClip.vue'

const ctx = useSpeakerContext()
</script>

<template>
  <SectionCard title="1. Source">
    <p class="dim">Tick the clip(s) to clone from. Several ticked clips are compared on the same lines with the same seed.</p>
    <RealClipList v-if="ctx.detail.value && (ctx.detail.value.summary.origin === 'real' || ctx.detail.value.clips.length)" :clips="ctx.detail.value.clips" />
    <DesignPanel v-if="ctx.detail.value?.design" />
    <SuppliedClip />
  </SectionCard>
</template>

<style scoped>
.dim { color: var(--dim); font-size: 12px; }
</style>
