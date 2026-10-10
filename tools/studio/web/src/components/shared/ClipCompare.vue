<script setup lang="ts">
import { useAudioPlayer } from '../../composables/useAudioPlayer'

export interface ClipItem {
  key: string
  label: string
  /** Hover text; defaults to the label. */
  title?: string
  path: string | null
  /** Alternative audio URL (e.g. the compressed copy); it also names the clip while it plays. */
  src?: string
  /** Second line in the A/B strip (file name, seed). Ignored by ClipCompare. */
  sub?: string
}
defineProps<{ clips: ClipItem[] }>()
const { play, playing } = useAudioPlayer()
const id = (c: ClipItem) => c.src ?? c.path
const start = (c: ClipItem) => (c.src ? play(c.src, c.src) : c.path && play(c.path))
</script>

<template>
  <div class="compare">
    <button
      v-for="c in clips"
      :key="c.key"
      class="clip"
      :class="{ 'is-playing': id(c) !== null && playing === id(c) }"
      :disabled="!c.path"
      :title="c.path ? (c.title ?? c.label) : 'no clip'"
      @click="start(c)"
    >
      {{ c.label }}
    </button>
  </div>
</template>

<style scoped>
.compare { display: flex; gap: 6px; flex-wrap: wrap; }
.clip { padding: 4px 10px; border: 1px solid var(--line-strong); border-radius: var(--r-md); background: var(--raised); color: var(--text); cursor: pointer; }
.clip:disabled { opacity: 0.45; cursor: default; }
.is-playing { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
</style>
