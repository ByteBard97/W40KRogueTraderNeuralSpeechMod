<script setup lang="ts">
import { computed } from 'vue'
import { SPEEDS, useGlobalAudio } from '../../composables/globalAudio'
import { blurAfterPointer } from '../../utils/keys'
import { formatPlayhead } from '../../utils/time'
import Btn from './Btn.vue'
import Icon from './Icon.vue'
import SeekTrack from './SeekTrack.vue'
import Seg from './Seg.vue'

/** The persistent bottom bar. Mount once (the shell does). `static` renders it in flow for the styleguide. */
defineProps<{ static?: boolean }>()
const a = useGlobalAudio()
const s = a.state
const speedOptions = SPEEDS.map((v) => ({ value: v, label: `${v}×` }))
const idle = computed(() => !a.hasClip.value)

function toggle(e: MouseEvent) {
  blurAfterPointer(e)
  a.toggle()
}
const seekFraction = (f: number) => a.seek(f * s.duration)
</script>

<template>
  <div class="player" :class="{ static: static }" role="region" aria-label="Audio player">
    <div class="np">
      <span class="t">{{ idle ? 'Nothing playing' : s.title }}</span>
      <span class="s">{{ idle ? 'Press a play button' : s.subtitle }}</span>
    </div>
    <div class="ctl">
      <Btn variant="ghost" icon label="Previous clip (,)" :disabled="!s.transport.prev" @click="s.transport.prev?.()"><Icon name="prev" /></Btn>
      <button type="button" class="play lg" :class="{ on: s.isPlaying }" :disabled="idle" :aria-label="s.isPlaying ? 'Pause (Space)' : 'Play (Space)'" @click="toggle">
        <Icon :name="s.isPlaying ? 'pause' : 'play'" />
      </button>
      <Btn variant="ghost" icon label="Next clip (.)" :disabled="!s.transport.next" @click="s.transport.next?.()"><Icon name="next" /></Btn>
    </div>
    <div class="seek">
      <span class="time num">{{ formatPlayhead(s.current) }}</span>
      <SeekTrack :model-value="a.progress.value" label="Seek" :disabled="idle" :value-text="`${formatPlayhead(s.current)} of ${formatPlayhead(s.duration)}`" @update:model-value="seekFraction" />
      <span class="time num">{{ formatPlayhead(s.duration) }}</span>
    </div>
    <div class="opts">
      <Seg :model-value="s.rate" :options="speedOptions" aria-label="Speed" @update:model-value="(v) => a.setRate(Number(v))" />
      <Btn variant="ghost" size="sm" :pressed="s.loop" @click="a.setLoop(!s.loop)"><Icon name="loop" :size="14" />Loop</Btn>
      <span class="vol"><Icon name="volume" /><SeekTrack class="voltrack" :model-value="s.volume" label="Volume" @update:model-value="a.setVolume" /></span>
    </div>
  </div>
</template>

<style scoped>
.player { position: fixed; left: 0; right: 0; bottom: 0; z-index: var(--z-player); min-height: var(--bar-h); display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-4); padding: var(--s-2) var(--s-5); background: rgba(19, 20, 23, 0.97); border-top: 1px solid var(--line-strong); box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.35); }
.static { position: relative; border: 1px solid var(--line-strong); border-radius: var(--r-lg); }
.np { display: flex; flex-direction: column; min-width: 0; flex: 0 1 260px; }
.t { font-weight: 600; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.s { font-size: var(--fs-xs); color: var(--text-3); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ctl { display: flex; align-items: center; gap: var(--s-1); }
.seek { flex: 1 1 260px; display: flex; align-items: center; gap: var(--s-2); min-width: 180px; }
.time { font-size: var(--fs-sm); color: var(--text-2); white-space: nowrap; }
.opts { display: flex; align-items: center; gap: var(--s-2); }
.vol { display: inline-flex; align-items: center; gap: 6px; color: var(--text-3); }
.voltrack { width: 72px; flex: none; }
.play { width: var(--hit-lg); height: var(--hit-lg); flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); cursor: pointer; padding: 0; }
.play:hover { border-color: var(--accent); color: var(--accent-hi); }
.play.on { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.play:disabled { color: var(--text-off); border-color: var(--line); background: transparent; cursor: not-allowed; opacity: 1; }
@media (max-width: 640px) {
  .player { padding: var(--s-2) var(--s-3); }
  .np { flex: 1 1 60%; }
  .opts { display: none; }
  .seek { order: 5; flex: 1 1 100%; }
}
</style>
