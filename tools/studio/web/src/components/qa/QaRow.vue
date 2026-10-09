<script setup lang="ts">
import { computed } from 'vue'
import type { QaClip, QaFx, QaVerdictValue } from '../../api/types'
import { fxUrl } from '../../utils/fileUrl'
import { QA_TAGS } from '../../utils/qaKeys'
import ClipCompare, { type ClipItem } from '../shared/ClipCompare.vue'

const props = defineProps<{ clip: QaClip; selected: boolean; fx: QaFx | null }>()
const emit = defineEmits<{
  select: []
  verdict: [value: QaVerdictValue | null]
  tags: [tags: string[]]
  note: [note: string]
}>()

const tags = computed(() => props.clip.verdict?.tags ?? [])

const item = (key: string, label: string, path: string | null, compress: boolean): ClipItem => ({
  key, label, path, src: path && compress && props.fx ? fxUrl(path, props.fx) : undefined,
})
const clips = computed<ClipItem[]>(() => [
  item('clip', props.fx ? `clip (${props.fx})` : 'clip', props.clip.wav, true),
  item('ref', 'reference', props.clip.ref_path || null, false),
  item('old', 'earlier render', props.clip.old, true),
  ...props.clip.real.map((r, i) => ({ ...item(`real${i}`, r.full_line ? `${r.label} (full line)` : r.label, r.path, false), title: r.text })),
])

const toggleTag = (t: string) => emit('tags', tags.value.includes(t) ? tags.value.filter((x) => x !== t) : [...tags.value, t])
const toggleVerdict = (v: QaVerdictValue) => emit('verdict', props.clip.verdict?.verdict === v ? null : v)
</script>

<template>
  <div class="row" :class="{ selected, good: clip.verdict?.verdict === 'good', bad: clip.verdict?.verdict === 'bad' }" @click="emit('select')">
    <div class="meta dim">
      <b class="sp">{{ clip.speaker }}</b>
      <span>{{ clip.engine }}</span>
      <span v-if="clip.ref">ref {{ clip.ref }}</span>
      <span>{{ clip.dur }} s</span>
      <span>{{ clip.cps }} chars/s</span>
      <span v-if="clip.emotion">{{ clip.emotion }}</span>
      <span v-if="clip.wer !== null">WER {{ clip.wer }}</span>
    </div>
    <div class="text">{{ clip.text }}</div>
    <div v-if="clip.context" class="dim">sent as: {{ clip.context }}</div>
    <div v-if="clip.flags.length" class="flags">
      <span v-for="g in clip.flags" :key="g" class="flag">{{ g }}</span>
    </div>
    <div v-if="clip.heard" class="dim" data-heard>heard: {{ clip.heard }}</div>
    <div class="actions">
      <ClipCompare :clips="clips" />
      <button class="v good" :class="{ on: clip.verdict?.verdict === 'good' }" data-good @click.stop="toggleVerdict('good')">Good</button>
      <button class="v bad" :class="{ on: clip.verdict?.verdict === 'bad' }" data-bad @click.stop="toggleVerdict('bad')">Bad</button>
    </div>
    <div class="judging" @click.stop>
      <button v-for="t in QA_TAGS" :key="t" class="tag" :class="{ on: tags.includes(t) }" data-tag @click="toggleTag(t)">{{ t }}</button>
      <input class="note" data-note :value="clip.verdict?.note" placeholder="note" @change="emit('note', ($event.target as HTMLInputElement).value)" />
    </div>
  </div>
</template>

<style scoped>
.row { border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; margin: 6px 0; background: var(--card); }
.row.selected { border-color: var(--acc); }
.row.good { border-left: 4px solid var(--ok); }
.row.bad { border-left: 4px solid var(--bad); }
.meta { display: flex; gap: 10px; flex-wrap: wrap; }
.sp { color: var(--acc); }
.text { margin: 4px 0; }
.dim { color: var(--dim); font-size: 12px; }
.flags { display: flex; gap: 6px; flex-wrap: wrap; margin: 2px 0; }
.flag { border: 1px solid var(--bad); color: var(--bad); border-radius: 10px; padding: 0 7px; font-size: 11px; }
.actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 4px; }
.v.good.on { background: var(--ok); color: var(--on-acc); border-color: var(--ok); }
.v.bad.on { background: var(--bad); color: var(--on-acc); border-color: var(--bad); }
.judging { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.tag { padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.tag.on { background: var(--acc); color: var(--on-acc); border-color: var(--acc); }
.note { flex: 1; min-width: 160px; }
</style>
