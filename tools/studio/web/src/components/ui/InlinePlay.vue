<script setup lang="ts">
import { computed } from 'vue'
import { useGlobalAudio } from '../../composables/globalAudio'
import { blurAfterPointer } from '../../utils/keys'
import { formatPlayhead } from '../../utils/time'
import Icon from './Icon.vue'

const WAVE_BARS = 40
const WAVE_MIN = 18
const WAVE_SPAN = 77
const HASH_MUL = 31

/** Round play button that loads `id` into the app-wide player. Shows playing state for its own clip only. */
const props = withDefaults(
  defineProps<{
    /** Clip identity: a repo path (played through /file) or any key when `src` is given. */
    id: string | null
    /** Audio URL when it is not a plain repo path. */
    src?: string
    title?: string
    subtitle?: string
    large?: boolean
    /** Mini waveform with progress in brass. The bars are decorative (derived from the id), not real analysis. */
    waveform?: boolean
    /** Why there is no audio; shown as the tooltip on the disabled button. */
    unavailableReason?: string
  }>(),
  { src: undefined, title: undefined, subtitle: undefined, unavailableReason: 'No audio' },
)
const audio = useGlobalAudio()
const available = computed(() => props.id !== null && props.id !== '')
const active = computed(() => available.value && audio.state.id === props.id)
const isPlaying = computed(() => active.value && audio.state.isPlaying)
const progress = computed(() => (active.value ? audio.progress.value : 0))

const bars = computed(() => {
  let h = [...(props.id ?? '')].reduce((a, c) => (a * HASH_MUL + c.charCodeAt(0)) >>> 0, 7)
  return Array.from({ length: WAVE_BARS }, () => {
    h = (h * 1664525 + 1013904223) >>> 0
    return WAVE_MIN + (h % WAVE_SPAN)
  })
})
const playedBars = computed(() => Math.round(progress.value * WAVE_BARS))
const clock = computed(() => (active.value ? `${formatPlayhead(audio.state.current)} / ${formatPlayhead(audio.state.duration)}` : ''))

function click(e: MouseEvent) {
  blurAfterPointer(e)
  if (!available.value) return
  audio.play(props.id as string, props.src, { title: props.title, subtitle: props.subtitle })
}
</script>

<template>
  <span class="inline-play">
    <button
      type="button"
      class="play"
      :class="{ on: isPlaying, lg: large }"
      :disabled="!available"
      :aria-label="!available ? unavailableReason : isPlaying ? 'Pause' : 'Play'"
      :aria-pressed="available ? isPlaying : undefined"
      :title="available ? undefined : unavailableReason"
      @click="click"
    >
      <Icon :name="isPlaying ? 'pause' : 'play'" :size="large ? 16 : 12" />
    </button>
    <template v-if="waveform">
      <span class="wave" aria-hidden="true"><i v-for="(h, n) in bars" :key="n" :class="{ p: n < playedBars }" :style="{ height: `${h}%` }" /></span>
      <span class="num muted clock">{{ clock }}</span>
    </template>
  </span>
</template>

<style scoped>
.inline-play { display: inline-flex; align-items: center; gap: var(--s-2); min-width: 0; }
.play { width: var(--hit); height: var(--hit); flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); cursor: pointer; padding: 0; }
.play:hover { border-color: var(--accent); color: var(--accent-hi); }
.on { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.on:hover { color: var(--accent-ink); }
.lg { width: var(--hit-lg); height: var(--hit-lg); }
.play:disabled { color: var(--text-off); border-color: var(--line); background: transparent; cursor: not-allowed; opacity: 1; }
.wave { display: flex; align-items: center; gap: 2px; height: 24px; flex: 1 1 auto; min-width: 60px; }
.wave i { flex: 1 1 0; background: var(--n-5); border-radius: 1px; min-width: 2px; }
.wave i.p { background: var(--accent); }
.clock { font-size: var(--fs-sm); white-space: nowrap; }
</style>
