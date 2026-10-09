<script setup lang="ts">
import { useAudioPlayer } from '../../composables/useAudioPlayer'

export interface ClipItem {
  key: string
  label: string
  path: string | null
}
defineProps<{ clips: ClipItem[] }>()
const { play, playing } = useAudioPlayer()
</script>

<template>
  <div class="compare">
    <button
      v-for="c in clips"
      :key="c.key"
      class="clip"
      :class="{ 'is-playing': c.path !== null && playing === c.path }"
      :disabled="!c.path"
      :title="c.path ? c.label : 'no clip'"
      @click="c.path && play(c.path)"
    >
      {{ c.label }}
    </button>
  </div>
</template>

<style scoped>
.compare { display: flex; gap: 6px; flex-wrap: wrap; }
.clip { padding: 4px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg); cursor: pointer; }
.clip:disabled { opacity: 0.45; cursor: default; }
.is-playing { background: var(--acc); color: #0b1220; border-color: var(--acc); }
</style>
