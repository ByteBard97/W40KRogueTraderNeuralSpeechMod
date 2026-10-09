<script setup lang="ts">
import type { RealClip } from '../../api/types'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import EmptyState from '../shared/EmptyState.vue'

defineProps<{ clips: RealClip[] }>()
const ctx = useSpeakerContext()
const { play } = useAudioPlayer()

function toggle(id: string, on: boolean) {
  const next = new Set(ctx.selectedSources.value)
  on ? next.add(`real:${id}`) : next.delete(`real:${id}`)
  ctx.selectedSources.value = next
}
</script>

<template>
  <EmptyState v-if="!clips.length" message="No real clips for this speaker." />
  <div v-for="c in clips" :key="c.id" class="clip">
    <input type="checkbox" :checked="ctx.selectedSources.value.has(`real:${c.id}`)" @change="toggle(c.id, ($event.target as HTMLInputElement).checked)" />
    <button class="play" @click="play(c.wav)">▶</button>
    <div>
      <span class="chip" :class="{ on: c.curated_rank }">{{ c.curated_rank ? `curated #${c.curated_rank}` : 'uncurated' }}</span>
      <span class="chip">{{ c.duration.toFixed(1) }}s</span>
      <span v-if="c.noise_db !== null" class="chip">noise {{ c.noise_db }} dB</span>
      <span class="chip">{{ c.id }}</span>
      <div class="dim">{{ c.text.slice(0, 200) }}</div>
    </div>
  </div>
</template>

<style scoped>
.clip { display: grid; grid-template-columns: 22px 30px 1fr; gap: 6px; padding: 6px 0; border-top: 1px solid var(--line); align-items: start; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); margin-right: 4px; }
.chip.on { border-color: var(--acc); color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
</style>
