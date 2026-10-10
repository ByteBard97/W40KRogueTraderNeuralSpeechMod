<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useGlobalAudio } from '../../composables/globalAudio'
import type { QaClip, QaFx, QaVerdictValue } from '../../api/types'
import { fxUrl } from '../../utils/fileUrl'
import { blurAfterPointer } from '../../utils/keys'
import { formatClock } from '../../utils/time'
import { FLAG_WHY, QA_TAGS, tagKey } from '../../utils/qaKeys'
import Btn from '../ui/Btn.vue'
import Flag from '../ui/Flag.vue'
import InlineError from '../ui/InlineError.vue'
import JudgePair from '../ui/JudgePair.vue'
import Kbd from '../ui/Kbd.vue'
import SavedIndicator from '../ui/SavedIndicator.vue'
import ABCompareStrip from '../ui/ABCompareStrip.vue'
import type { ClipItem } from '../shared/ClipCompare.vue'

const SLOT_KEYS = ['A', 'S', 'D', 'F']
const props = defineProps<{ clip: QaClip; position: number; total: number; fx: QaFx | '' }>()
const emit = defineEmits<{
  verdict: [value: QaVerdictValue | null]
  tags: [tags: string[]]
  note: [note: string]
  nextUnjudged: []
}>()

const audio = useGlobalAudio()
const slot = ref('clip')
const verdict = computed(() => props.clip.verdict?.verdict ?? null)
const tags = computed(() => props.clip.verdict?.tags ?? [])

const item = (key: string, label: string, sub: string, path: string | null, compress: boolean): ClipItem => ({
  key, label, sub, path, src: path && compress && props.fx ? fxUrl(path, props.fx) : undefined,
})
const clips = computed<ClipItem[]>(() => {
  const c = props.clip
  const real: ClipItem[] = c.real.length
    ? c.real.map((r, i) => ({ ...item(`real${i}`, r.label, r.full_line ? 'game voice, full line' : 'game voice line', r.path, false), title: r.text }))
    : [{ key: 'real', label: 'Real line', sub: 'not voiced in game', path: null }]
  return [
    item('clip', 'Clip', `${c.engine} · ${formatClock(c.dur)}${props.fx ? ` · ${props.fx}` : ''}`, c.wav, true),
    item('ref', 'Clone reference', c.ref || 'none', c.ref_path || null, false),
    item('old', 'Earlier render', c.old ? 'previous take' : 'none for this run', c.old, true),
    ...real,
  ]
})
watch(() => props.clip.guid, () => { slot.value = 'clip' })
// A slot that stops existing (clip changed, its path vanished) falls back to the clip itself.
watch(clips, (list) => { if (!list.some((c) => c.key === slot.value && (c.src ?? c.path))) slot.value = 'clip' })

/** Space: play or pause the chosen source, loading it first when the player holds something else. */
function playSelected() {
  const c = clips.value.find((x) => x.key === slot.value)
  const id = c && (c.src ?? c.path)
  if (c && id) audio.play(id, c.src, { title: `${props.clip.speaker} · ${c.label}`, subtitle: c.sub ?? '' })
}
defineExpose({ playSelected })

const toggleTag = (t: string) => emit('tags', tags.value.includes(t) ? tags.value.filter((x) => x !== t) : [...tags.value, t])
const note = ref(props.clip.verdict?.note ?? '')
let sent = note.value   // Enter saves and then blurs, which fires `change`: do not save the same text twice
watch(() => [props.clip.guid, props.clip.verdict?.note], () => { note.value = sent = props.clip.verdict?.note ?? '' })
function saveNote(e?: Event) {
  if (note.value !== sent) { sent = note.value; emit('note', note.value) }
  if (e && (e as KeyboardEvent).key === 'Enter') (e.target as HTMLElement).blur()
}
</script>

<template>
  <article class="clip" aria-label="Current clip">
    <div class="meta">
      <b class="who">{{ clip.speaker }}</b>
      <span class="mono">{{ clip.engine }}</span><span class="sep">·</span>
      <span v-if="clip.ref">ref <span class="mono">{{ clip.ref }}</span></span><span v-if="clip.ref" class="sep">·</span>
      <span class="num">{{ clip.dur }} s</span><span class="sep">·</span>
      <span class="num">{{ clip.cps }} chars/s</span>
      <template v-if="clip.emotion"><span class="sep">·</span><span>{{ clip.emotion }}</span></template>
      <span class="muted num pos">clip {{ position.toLocaleString('en-US') }} of {{ total.toLocaleString('en-US') }}</span>
    </div>
    <p class="cliptext" data-text>{{ clip.text }}</p>
    <div v-if="clip.context" class="sentas" data-context>
      <span class="sentas-h">Sent to the model as</span><br />{{ clip.context }}
    </div>
    <div v-if="clip.flags.length" class="flagrow">
      <template v-for="g in clip.flags" :key="g">
        <Flag :title="FLAG_WHY[g]">{{ g }}</Flag><span v-if="FLAG_WHY[g]" class="why">{{ FLAG_WHY[g] }}</span>
      </template>
    </div>
    <InlineError v-if="clip.heard" title="ASR" data-heard>
      <div>heard <b>“{{ clip.heard }}”</b><template v-if="clip.wer !== null"> · word error rate <b class="num">{{ clip.wer }}</b></template></div>
    </InlineError>

    <ABCompareStrip v-model="slot" :clips="clips" :keys="SLOT_KEYS" hotkeys />
    <JudgePair :model-value="verdict" @update:model-value="emit('verdict', $event)" />

    <div class="why-bad">
      <div class="muted hint">What is wrong? Tags also mark the clip bad · keys 1–9, 0</div>
      <div class="tags">
        <button v-for="(t, i) in QA_TAGS" :key="t" type="button" class="chip" :aria-pressed="tags.includes(t)" data-tag @click="blurAfterPointer($event); toggleTag(t)">
          <Kbd>{{ tagKey(i) }}</Kbd>{{ t }}
        </button>
      </div>
      <label class="field note-field"><span class="lbl">Note</span><input v-model="note" data-note placeholder="Optional · Enter saves" @change="saveNote()" @keydown.enter="saveNote($event)" /></label>
    </div>

    <div class="foot">
      <SavedIndicator v-if="verdict" :ago="verdict" data-saved />
      <span v-else class="muted" data-saved>Unjudged</span>
      <span class="acts">
        <Btn variant="ghost" kbd="U" :disabled="!verdict" data-clear @click="emit('verdict', null)">Clear verdict</Btn>
        <Btn kbd="N" data-next-unjudged @click="emit('nextUnjudged')">Next unjudged</Btn>
      </span>
    </div>
  </article>
</template>

<style scoped>
.clip { display: flex; flex-direction: column; gap: var(--s-4); padding: 20px 22px; background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--r-lg); min-width: 0; }
.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; font-size: 13px; color: var(--text-2); }
.who { color: var(--accent-hi); font-weight: 600; font-size: 15px; }
.sep { color: var(--n-6); }
.pos { margin-left: auto; font-size: var(--fs-sm); }
.cliptext { font-size: var(--fs-xl); line-height: 1.45; color: var(--text); margin: 0; text-wrap: pretty; overflow-wrap: anywhere; }
.sentas { font-size: 13px; color: var(--text-3); padding: var(--s-2) var(--s-3); background: var(--n-1); border-radius: var(--r-md); overflow-wrap: anywhere; }
.sentas-h { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }
.flagrow { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.why { font-size: var(--fs-sm); color: var(--text-3); }
.why-bad { display: flex; flex-direction: column; gap: var(--s-2); }
.hint { font-size: var(--fs-sm); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 0 10px; border-radius: var(--r-pill); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text-2); font-size: 13px; cursor: pointer; }
.chip:hover { border-color: var(--n-6); color: var(--text); }
.chip[aria-pressed="true"] { border-color: var(--bad-line); background: var(--bad-tint); color: var(--bad); }
.note-field { width: 100%; }
.foot { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.acts { margin-left: auto; display: flex; gap: var(--s-2); }
@media (max-width: 640px) { .clip { padding: var(--s-3); } .cliptext { font-size: 17px; } }
</style>
