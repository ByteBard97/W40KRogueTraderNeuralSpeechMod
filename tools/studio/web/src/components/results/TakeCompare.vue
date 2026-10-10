<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Line, Take } from '../../api/types'
import { useGlobalAudio } from '../../composables/globalAudio'
import { blurAfterPointer } from '../../utils/keys'

const props = defineProps<{ take: Take; line: Line | null; speaker: string }>()
const audio = useGlobalAudio()
const selected = ref('clone')

const dur = (s: number | null | undefined) => (typeof s === 'number' ? `${s.toFixed(1)} s` : '')
/** Real is always empty: an unvoiced line has no real recording to compare with. */
const clips = computed(() => [
  { key: 'real', label: 'Real', path: null as string | null, sub: 'none' },
  { key: 'bank', label: 'Bank', path: props.line?.baseline ?? null, sub: props.line?.baseline ? dur(props.line.dur) || 'bank render' : 'none' },
  { key: 'clone', label: 'Clone', path: props.take.raw, sub: dur(props.take.audio_s) || 'raw clone' },
  { key: 'fx', label: '+ FX', path: props.take.fx ? `${props.take.fx.wav}?v=${props.take.fx.v}` : null, sub: props.take.fx ? dur(props.take.fx.dur) || 'processed' : 'none' },
])
const owns = computed(() => clips.value.some((c) => c.path !== null && c.path === audio.state.id))

function choose(c: { key: string; label: string; path: string | null }) {
  if (!c.path) return
  selected.value = c.key
  const meta = { title: `${props.speaker} · ${c.label.toLowerCase()} · ${props.take.id}`, subtitle: c.path.split('?')[0] }
  if (owns.value && audio.state.id !== c.path) audio.switchTo(c.path, undefined, meta, 'fraction')
  else audio.play(c.path, undefined, meta)
}
const click = (e: MouseEvent, c: (typeof clips.value)[number]) => {
  blurAfterPointer(e)
  choose(c)
}
</script>

<template>
  <div class="ab" role="group" aria-label="Compare versions">
    <button v-for="c in clips" :key="c.key" type="button" :aria-pressed="c.key === selected && !!c.path" :disabled="!c.path" :title="c.path ? undefined : `No ${c.label.toLowerCase()} clip`" @click="click($event, c)">
      <b>{{ c.label }}</b><span class="num muted">{{ c.sub }}</span>
    </button>
  </div>
</template>

<style scoped>
.ab { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
button { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; min-height: 44px; padding: 6px 8px; border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text-2); font-size: var(--fs-sm); cursor: pointer; text-align: left; }
button:hover { border-color: var(--n-6); color: var(--text); }
button[aria-pressed='true'] { border-color: var(--accent); background: var(--accent-tint); color: var(--text); }
button:disabled { border-style: dashed; opacity: 0.55; cursor: not-allowed; }
span { font-size: var(--fs-xs); }
@media (max-width: 640px) { .ab { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
