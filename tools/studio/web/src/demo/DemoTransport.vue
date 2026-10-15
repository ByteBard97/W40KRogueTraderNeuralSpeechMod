<script setup lang="ts">
import { ref } from 'vue'
import { RECORD_SECONDS } from './useDemoAudio'

const GAP_MAX_S = 2
const GAP_STEP_S = 0.1

defineProps<{
  playing: boolean
  bypass: boolean
  gap: number
  source: string
  referenceName: string
  recording: boolean
  recordLeft: number
}>()
const emit = defineEmits<{
  'test-signal': []
  file: [file: File]
  record: []
  reference: [file: File | null]
  play: []
  stop: []
  bypass: [value: boolean]
  gap: [seconds: number]
}>()

const over = ref(false)
const pick = (e: Event) => {
  const el = e.target as HTMLInputElement
  const f = el.files?.[0]
  if (f) emit('file', f)
  el.value = ''
}
const pickRef = (e: Event) => {
  const el = e.target as HTMLInputElement
  emit('reference', el.files?.[0] ?? null)
  el.value = ''
}
function drop(e: DragEvent) {
  over.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) emit('file', f)
}
</script>

<template>
  <div class="transport" :class="{ over }" data-testid="transport" @dragover.prevent="over = true" @dragleave="over = false" @drop.prevent="drop">
    <div class="group">
      <button type="button" class="btn primary" data-testid="test-signal" @click="emit('test-signal')">Play test signal</button>
      <label class="btn file">Load a voice clip<input type="file" accept="audio/*" data-testid="file-input" @change="pick"></label>
      <button type="button" class="btn" data-testid="record" :disabled="recording" @click="emit('record')">{{ recording ? `Recording, ${recordLeft}s` : `Record ${RECORD_SECONDS} seconds` }}</button>
      <span class="hint">or drop an audio file anywhere on this bar</span>
    </div>
    <div class="group">
      <button type="button" class="btn" data-testid="play" :disabled="!source" @click="playing ? emit('stop') : emit('play')">{{ playing ? 'Stop' : 'Play loop' }}</button>
      <label class="check"><input type="checkbox" data-testid="bypass" :checked="bypass" @change="emit('bypass', ($event.target as HTMLInputElement).checked)"> Raw (bypass)</label>
      <label class="gap">Gap {{ gap.toFixed(1) }}s
        <input type="range" data-testid="gap" min="0" :max="GAP_MAX_S" :step="GAP_STEP_S" :value="gap" @input="emit('gap', Number(($event.target as HTMLInputElement).value))">
      </label>
      <span class="now" data-testid="source">{{ source ? `Source: ${source}` : 'No source yet' }}</span>
    </div>
    <div class="group">
      <label class="btn file">Reference voice (optional)<input type="file" accept="audio/*" data-testid="reference-input" @change="pickRef"></label>
      <template v-if="referenceName">
        <span class="now" data-testid="reference-name">Overlay: {{ referenceName }}</span>
        <button type="button" class="btn" data-testid="reference-clear" @click="emit('reference', null)">Clear</button>
      </template>
      <span v-else class="hint">Its average spectrum is drawn as a dashed line on the monitor.</span>
    </div>
  </div>
</template>

<style scoped>
.transport { display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-3); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); }
.transport.over { border-color: var(--accent); background: var(--accent-tint); }
.group { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); }
.btn { display: inline-flex; align-items: center; min-height: var(--hit); padding: 0 var(--s-3); border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); font-size: var(--fs-md); font-weight: 500; cursor: pointer; }
.btn:hover { background: var(--inset); }
.btn:disabled { color: var(--text-off); border-color: var(--line); background: transparent; cursor: not-allowed; }
.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.primary:hover { background: var(--accent-hi); }
.file input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.file { position: relative; }
.file:focus-within { outline: 2px solid var(--focus); outline-offset: 2px; }
.check, .gap { display: flex; align-items: center; gap: var(--s-2); font-size: var(--fs-sm); color: var(--text-2); }
.hint, .now { font-size: var(--fs-sm); color: var(--text-3); }
.now { color: var(--text-2); }
</style>
