<script setup lang="ts">
import type { RealClip } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import EmptyState from '../shared/EmptyState.vue'
import DataRow from '../ui/DataRow.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import Tag from '../ui/Tag.vue'

const TEXT_CHARS = 200
defineProps<{ clips: RealClip[] }>()
const ctx = useSpeakerContext()

function toggle(id: string, on: boolean) {
  const next = new Set(ctx.selectedSources.value)
  if (on) next.add(`real:${id}`)
  else next.delete(`real:${id}`)
  ctx.selectedSources.value = next
}
</script>

<template>
  <EmptyState v-if="!clips.length" message="No real clips for this speaker." />
  <div v-else class="list">
    <DataRow v-for="c in clips" :key="c.id" :selected="ctx.selectedSources.value.has(`real:${c.id}`)">
      <template #lead>
        <input type="checkbox" :aria-label="`Clone from ${c.id}`" :checked="ctx.selectedSources.value.has(`real:${c.id}`)" @change="toggle(c.id, ($event.target as HTMLInputElement).checked)" />
        <InlinePlay :id="c.wav" :title="`${ctx.detail.value?.summary.name ?? ''} · ${c.id}`" :subtitle="c.wav" />
      </template>
      <span class="text">{{ c.text.slice(0, TEXT_CHARS) }}</span>
      <template #meta>
        <Tag :variant="c.curated_rank ? 'designed' : 'plain'">{{ c.curated_rank ? `curated #${c.curated_rank}` : 'uncurated' }}</Tag>
        <Tag>{{ c.duration.toFixed(1) }} s</Tag>
        <Tag v-if="c.noise_db !== null">noise {{ c.noise_db }} dB</Tag>
        <Tag class="id">{{ c.id }}</Tag>
      </template>
    </DataRow>
  </div>
</template>

<style scoped>
.list { border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--surface); }
input { accent-color: var(--accent); width: 16px; height: 16px; }
.text { font-size: 13px; color: var(--text-2); overflow-wrap: anywhere; }
.id { font-family: var(--font-mono); overflow-wrap: anywhere; }
</style>
