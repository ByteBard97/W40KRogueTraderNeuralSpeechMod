<script setup lang="ts">
import { useGlobalAudio } from '../../composables/globalAudio'
import { blurAfterPointer } from '../../utils/keys'
import Icon from '../ui/Icon.vue'

/** A cloned real line, as a pill that plays it in the global player. The text is cut by CSS, never by the data. */
const props = defineProps<{ file: string; text: string; title: string; pUs?: number | null }>()
const audio = useGlobalAudio()
const toggle = (e: MouseEvent) => {
  blurAfterPointer(e)
  audio.play(props.file, undefined, { title: props.title, subtitle: props.file })
}
</script>

<template>
  <button type="button" class="pill" :aria-pressed="audio.state.id === file && audio.state.isPlaying" :title="text" @click="toggle">
    <Icon :name="audio.state.id === file && audio.state.isPlaying ? 'pause' : 'play'" :size="10" />
    <span>{{ text }}</span>
    <i v-if="pUs !== undefined && pUs !== null" class="num" :class="{ hot: pUs > 0.5 }">{{ pUs.toFixed(2) }}</i>
  </button>
</template>

<style scoped>
.pill { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; max-width: 260px; padding: 0 10px 0 8px; border-radius: var(--r-pill); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text-2); font-size: var(--fs-sm); cursor: pointer; }
.pill:hover { border-color: var(--accent); color: var(--text); }
.pill[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-tint); color: var(--text); }
.pill span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pill i { font-style: normal; font-size: var(--fs-xs); color: var(--good); }
.pill i.hot { color: var(--bad); }
</style>
