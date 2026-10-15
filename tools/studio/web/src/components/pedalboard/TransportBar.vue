<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../../api/client'
import type { LabLine, LabSpeaker } from '../../api/labTypes'
import type { RefSpeaker } from '../../api/referenceApi'
import { fileUrl } from '../../utils/fileUrl'

const props = withDefaults(defineProps<{ playing: boolean; refSpeakers: RefSpeaker[]; bypass?: boolean; gap?: number; reference?: string }>(), {
  bypass: false, gap: 0, reference: '',
})
const emit = defineEmits<{
  'load-clip': [url: string]
  play: []
  stop: []
  bypass: [value: boolean]
  gap: [seconds: number]
  reference: [speaker: string]
}>()

const GAP_MAX_S = 2
const GAP_STEP_S = 0.1
const LABEL_MAX = 80

const speakers = ref<LabSpeaker[]>([])
const lines = ref<LabLine[]>([])
const speaker = ref('')
const guid = ref('')
const failure = ref('')

const wavOf = (l: LabLine) => l.current?.wav ?? l.ref?.wav ?? ''
const labelOf = (l: LabLine) => (l.text.replace(/\{\/?n\}/g, '').trim() || l.guid).slice(0, LABEL_MAX)

async function chooseSpeaker(name: string) {
  speaker.value = name
  guid.value = ''
  lines.value = []
  if (!name) return
  try {
    lines.value = (await api.labLines(name)).lines.filter((l) => wavOf(l))
    failure.value = ''
  } catch (e) {
    failure.value = e instanceof Error ? e.message : String(e)
  }
  if (props.refSpeakers.some((r) => r.speaker === name)) emit('reference', name)
}

function chooseLine(id: string) {
  guid.value = id
  const l = lines.value.find((x) => x.guid === id)
  if (l) emit('load-clip', fileUrl(wavOf(l)))
}

onMounted(async () => {
  try { speakers.value = await api.labSpeakers() } catch (e) { failure.value = e instanceof Error ? e.message : String(e) }
})

defineExpose({ chooseSpeaker, chooseLine })
</script>

<template>
  <div class="transport">
    <label>Speaker
      <select data-test="speaker" :value="speaker" @change="chooseSpeaker(($event.target as HTMLSelectElement).value)">
        <option value="">choose</option>
        <option v-for="s in speakers" :key="s.slug" :value="s.speaker">{{ s.speaker }} ({{ s.lines }})</option>
      </select>
    </label>
    <label class="grow">Line
      <select data-test="line" :value="guid" :disabled="!lines.length" @change="chooseLine(($event.target as HTMLSelectElement).value)">
        <option value="">choose</option>
        <option v-for="l in lines" :key="l.guid" :value="l.guid">{{ labelOf(l) }}</option>
      </select>
    </label>
    <button type="button" class="play" data-test="play" @click="playing ? emit('stop') : emit('play')">{{ playing ? 'Stop' : 'Play loop' }}</button>
    <label class="check"><input type="checkbox" data-test="bypass" :checked="bypass" @change="emit('bypass', ($event.target as HTMLInputElement).checked)"> Raw (bypass)</label>
    <label>Gap {{ gap.toFixed(1) }}s
      <input type="range" data-test="gap" min="0" :max="GAP_MAX_S" :step="GAP_STEP_S" :value="gap" @input="emit('gap', Number(($event.target as HTMLInputElement).value))">
    </label>
    <label>Game voice
      <select data-test="reference" :value="reference" @change="emit('reference', ($event.target as HTMLSelectElement).value)">
        <option value="">no reference</option>
        <option v-for="r in refSpeakers" :key="r.speaker" :value="r.speaker">{{ r.speaker }} ({{ r.clips }})</option>
      </select>
    </label>
    <span v-if="failure" class="err" role="alert">{{ failure }}</span>
  </div>
</template>

<style scoped>
.transport { display: flex; flex-wrap: wrap; align-items: end; gap: var(--s-3); padding: var(--s-3); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); }
label { display: flex; flex-direction: column; gap: var(--s-1); font-size: var(--fs-sm); color: var(--text-3); }
.grow { flex: 1 1 220px; min-width: 0; }
.check { flex-direction: row; align-items: center; color: var(--text-2); }
select { background: var(--inset); color: var(--text); border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: var(--s-1) var(--s-2); font-size: var(--fs-md); max-width: 100%; }
.play { background: var(--accent); color: var(--accent-ink); border: 0; border-radius: var(--r-sm); padding: var(--s-2) var(--s-4); font-weight: 600; cursor: pointer; }
.play:hover { background: var(--accent-hi); }
.err { color: var(--bad); font-size: var(--fs-sm); }
</style>
