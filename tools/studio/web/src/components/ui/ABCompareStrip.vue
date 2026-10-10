<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useGlobalAudio } from '../../composables/globalAudio'
import { blurAfterPointer, isTypingTarget } from '../../utils/keys'
import { formatPlayhead } from '../../utils/time'
import type { ClipItem } from '../shared/ClipCompare.vue'
import Btn from './Btn.vue'
import Icon from './Icon.vue'
import Kbd from './Kbd.vue'
import SeekTrack from './SeekTrack.vue'
import Seg from './Seg.vue'

const MAX_HOTKEY_SLOTS = 4
const KEEP_OPTIONS = [
  { value: 'fraction', label: 'Same point' },
  { value: 'seconds', label: 'Same second' },
]

/**
 * N labelled clips on one shared audio element. Switching clips keeps the playhead (as a fraction of each clip by default, or
 * as absolute seconds). A clip with no path is shown disabled. `hotkeys` binds 1-4 on the document; the page should enable it
 * on one strip at a time. The strip also answers 1-4 while it has focus.
 */
const props = withDefaults(defineProps<{ clips: ClipItem[]; line?: string; modelValue?: string; hotkeys?: boolean }>(), { line: undefined, modelValue: undefined })
const emit = defineEmits<{ 'update:modelValue': [key: string] }>()

const audio = useGlobalAudio()
const keep = ref<'fraction' | 'seconds'>('fraction')
const own = ref<string | null>(null)

const idOf = (c: ClipItem) => c.src ?? c.path
const available = (c: ClipItem) => idOf(c) !== null && idOf(c) !== ''
const selectedKey = computed(() => props.modelValue ?? own.value ?? props.clips.find(available)?.key ?? null)
const selected = computed(() => props.clips.find((c) => c.key === selectedKey.value) ?? null)
const meta = (c: ClipItem) => ({ title: prefix() + c.label, subtitle: c.sub ?? c.path ?? '' })
const prefix = () => (props.line ? `${props.line} · ` : '')

const active = computed(() => !!selected.value && audio.state.id === idOf(selected.value))
const stripOwnsPlayer = computed(() => props.clips.some((c) => idOf(c) === audio.state.id))
const progress = computed(() => (active.value ? audio.progress.value : 0))
const urlOf = (c: ClipItem) => c.src

function pick(c: ClipItem) {
  const id = idOf(c)
  if (!id) return
  own.value = c.key
  emit('update:modelValue', c.key)
  if (stripOwnsPlayer.value && audio.state.id !== id) audio.switchTo(id, urlOf(c), meta(c), keep.value)
  else if (!stripOwnsPlayer.value) audio.play(id, urlOf(c), meta(c))
}
function togglePlay(e: MouseEvent) {
  blurAfterPointer(e)
  const c = selected.value
  const id = c && idOf(c)
  if (!c || !id) return
  audio.play(id, urlOf(c), meta(c))
}
const seekFraction = (f: number) => active.value && audio.seek(f * audio.state.duration)

function onKey(e: KeyboardEvent) {
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || isTypingTarget(e.target)) return
  const n = Number(e.key)
  if (!Number.isInteger(n) || n < 1 || n > Math.min(MAX_HOTKEY_SLOTS, props.clips.length)) return
  const c = props.clips[n - 1]
  if (!available(c)) return
  e.preventDefault()
  pick(c)
}
watch(
  () => props.hotkeys,
  (on, _, cleanup) => {
    if (!on) return
    document.addEventListener('keydown', onKey)
    cleanup(() => document.removeEventListener('keydown', onKey))
  },
  { immediate: true },
)
</script>

<template>
  <div class="ab" @keydown="!hotkeys && onKey($event)">
    <div class="head">
      <template v-if="line"><span>Line</span><b class="line">“{{ line }}”</b></template>
      <span class="hint">Switch <Kbd>1</Kbd>–<Kbd>{{ Math.min(clips.length, MAX_HOTKEY_SLOTS) }}</Kbd> · playhead kept</span>
    </div>
    <div class="slots" role="group" aria-label="Compare sources">
      <button
        v-for="(c, n) in clips"
        :key="c.key"
        type="button"
        class="slot"
        :aria-pressed="c.key === selectedKey"
        :disabled="!available(c)"
        :title="available(c) ? (c.title ?? c.label) : 'no clip'"
        @click="pick(c)"
      >
        <Kbd class="k">{{ n + 1 }}</Kbd>
        <span class="lbl"><b>{{ c.label }}</b><span>{{ available(c) ? (c.sub ?? c.path ?? '') : 'no clip' }}</span></span>
      </button>
    </div>
    <div class="track-row">
      <button type="button" class="play" :class="{ on: active && audio.state.isPlaying }" :disabled="!selected" :aria-label="active && audio.state.isPlaying ? 'Pause' : 'Play'" @click="togglePlay">
        <Icon :name="active && audio.state.isPlaying ? 'pause' : 'play'" :size="12" />
      </button>
      <span class="num muted time">{{ formatPlayhead(active ? audio.state.current : 0) }}</span>
      <SeekTrack :model-value="progress" label="Seek" :disabled="!active" @update:model-value="seekFraction" />
      <span class="num muted time">{{ formatPlayhead(active ? audio.state.duration : 0) }}</span>
      <Btn size="sm" variant="ghost" :pressed="audio.state.loop" kbd="L" @click="audio.setLoop(!audio.state.loop)">Loop</Btn>
    </div>
    <div class="foot">
      <span class="muted">Comparing <b class="cur">{{ selected?.label ?? 'nothing' }}</b>.</span>
      <Seg v-model="keep" :options="KEEP_OPTIONS" aria-label="Playhead on switch" />
    </div>
  </div>
</template>

<style scoped>
.ab { display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-3); border-radius: var(--r-lg); background: var(--n-1); border: 1px solid var(--line-strong); }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); font-size: var(--fs-sm); color: var(--text-3); }
.line { color: var(--text); }
.hint { margin-left: auto; }
.slots { display: flex; flex-wrap: wrap; gap: var(--s-2); }
.slot { flex: 1 1 140px; display: flex; align-items: center; gap: var(--s-2); min-height: var(--hit-lg); padding: 6px 10px; border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text-2); cursor: pointer; text-align: left; min-width: 0; }
.slot:hover { border-color: var(--n-6); color: var(--text); }
.slot[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-tint); color: var(--text); }
.slot:disabled { opacity: 0.55; cursor: not-allowed; border-style: dashed; }
.k { flex: none; }
.lbl { display: flex; flex-direction: column; min-width: 0; line-height: 1.2; }
.lbl b { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.lbl span { font-size: var(--fs-xs); color: var(--text-3); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.track-row { display: flex; align-items: center; gap: var(--s-2); }
.time { font-size: var(--fs-sm); }
.foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--s-2); font-size: 13px; }
.cur { color: var(--text); }
.play { width: var(--hit); height: var(--hit); flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); cursor: pointer; padding: 0; }
.play:hover { border-color: var(--accent); color: var(--accent-hi); }
.play.on { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.play:disabled { color: var(--text-off); border-color: var(--line); background: transparent; cursor: not-allowed; opacity: 1; }
</style>
