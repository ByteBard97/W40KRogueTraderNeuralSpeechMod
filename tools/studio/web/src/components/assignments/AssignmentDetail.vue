<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AssignmentItem, Bg3Voice } from '../../api/types'
import { fileUrl } from '../../utils/fileUrl'
import Btn from '../ui/Btn.vue'
import Flag from '../ui/Flag.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import SelectField from '../ui/SelectField.vue'
import Tag from '../ui/Tag.vue'

/** One character or group: who they are, what they say, which voice they got and why, the runners-up, and a way to pick a different voice. */
const props = defineProps<{ item: AssignmentItem; voice: Bg3Voice | null; voices: Bg3Voice[] }>()
const emit = defineEmits<{ pick: [bg3: string | null] }>()

const choice = ref('')
watch(() => props.item.key, () => { choice.value = '' })
const options = computed(() => [{ value: '', label: 'Pick another voice…' }, ...[...props.voices].sort((a, b) => a.name.localeCompare(b.name)).map((v) => ({ value: v.slug, label: `${v.name} (${v.gender})` }))])
const clip = (slug: string | undefined) => props.voices.find((v) => v.slug === slug)?.refs[0]?.wav ?? null
const learned = computed(() => Object.entries(props.item.learned ?? {}).map(([k, v]) => `${k}: ${v}`).join(', '))
function apply() { if (choice.value) { emit('pick', choice.value); choice.value = '' } }
</script>

<template>
  <section class="panel">
    <h2 class="name">{{ item.name }}</h2>
    <div class="tags">
      <Tag variant="slot" v-if="item.kind === 'group'">nameless group</Tag>
      <Tag>{{ item.lines }} lines</Tag>
      <Tag v-if="item.gender">{{ item.gender }}</Tag>
      <Tag v-if="item.species">{{ item.species }}</Tag>
      <Tag v-if="item.age">{{ item.age }}</Tag>
      <Tag v-if="item.conversation">{{ item.conversation }}</Tag>
      <Tag v-if="item.guessed_name" variant="real">name in the text: {{ item.guessed_name }}</Tag>
    </div>
    <p v-if="item.role" class="role">{{ item.role }}</p>
    <p v-if="item.description" class="desc">{{ item.description }}</p>
    <p v-if="learned" class="learned">Worked out from the game text: {{ learned }}</p>
    <ul v-if="item.samples.length" class="samples" aria-label="Lines they speak"><li v-for="(t, i) in item.samples" :key="i">{{ t }}</li></ul>

    <div v-if="item.status === 'assigned'" class="voicebox">
      <InlinePlay :id="clip(item.bg3)" :title="item.voice_name ?? ''" subtitle="BG3 reference clip" large unavailable-reason="No reference clip" />
      <div class="vinfo">
        <b class="vname">{{ item.voice_name }}</b>
        <span v-if="item.owner" class="mine">picked by you</span>
        <span v-if="voice" class="vmeta">{{ voice.lines.toLocaleString() }} lines of reference · used {{ voice.used_by.length }}× in hand casting</span>
        <ul class="why"><li v-for="r in item.reasons" :key="r">{{ r }}</li></ul>
        <Flag v-if="item.processed" tone="info">processed voice: renders at {{ item.steps }} steps</Flag>
      </div>
    </div>
    <div v-else class="needs">
      <Flag>Not enough is known to choose a voice: {{ item.missing?.join(', ') }}</Flag>
      <p class="hint">Pick a voice yourself below, or give the rules what is missing.</p>
    </div>

    <div v-if="item.alts.length" class="alts" aria-label="Other voices that fit">
      <span class="lbl">Runners-up</span>
      <div v-for="a in item.alts" :key="a.bg3" class="alt">
        <InlinePlay :id="clip(a.bg3)" :title="a.name" subtitle="BG3 reference clip" unavailable-reason="No reference clip" />
        <span>{{ a.name }}</span>
        <Btn size="sm" @click="emit('pick', a.bg3)">Use this</Btn>
      </div>
    </div>

    <div class="pick">
      <SelectField v-model="choice" label="Choose any voice" :options="options" />
      <Btn size="sm" variant="primary" :disabled="!choice" @click="apply">Use it</Btn>
      <Btn v-if="item.owner" size="sm" variant="ghost" @click="emit('pick', null)">Hand back to the rules</Btn>
    </div>

    <details v-if="item.research" class="research">
      <summary>What the game says about them</summary>
      <p v-if="item.research.conversation" class="hint">Conversation {{ item.research.conversation }}<template v-if="item.research.comment"> · {{ item.research.comment }}</template></p>
      <ul v-if="item.research.narration.length" class="samples" aria-label="Narration"><li v-for="(n, i) in item.research.narration" :key="i"><i>{{ n }}</i></li></ul>
      <ul class="samples" aria-label="Their lines"><li v-for="(l, i) in item.research.lines" :key="i">{{ l.say }}<span v-if="l.after" class="after"> (after: {{ l.after }})</span></li></ul>
    </details>
  </section>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: var(--s-3); padding: var(--s-4); background: var(--raised); border: 1px solid var(--line); border-radius: var(--r-lg); }
.name { margin: 0; font-family: var(--font-display); font-size: var(--fs-xl); letter-spacing: 0.03em; }
.tags { display: flex; flex-wrap: wrap; gap: var(--s-1); }
.role { margin: 0; color: var(--text-2); }
.desc { margin: 0; color: var(--text-2); font-style: italic; }
.learned, .hint { margin: 0; color: var(--text-3); font-size: var(--fs-sm); }
.samples { margin: 0; padding-left: var(--s-4); color: var(--text-2); font-size: var(--fs-sm); display: flex; flex-direction: column; gap: var(--s-1); }
.after { color: var(--text-3); }
.voicebox { display: flex; gap: var(--s-3); align-items: flex-start; padding: var(--s-3); background: var(--inset); border-radius: var(--r-md); }
.vinfo { display: flex; flex-direction: column; gap: var(--s-1); min-width: 0; }
.vname { font-size: var(--fs-lg); color: var(--accent-hi); }
.mine { color: var(--good); font-size: var(--fs-sm); font-weight: 600; }
.vmeta { color: var(--text-3); font-size: var(--fs-xs); }
.why { margin: 0; padding-left: var(--s-4); color: var(--text-2); font-size: var(--fs-sm); }
.needs { display: flex; flex-direction: column; gap: var(--s-2); }
.alts { display: flex; flex-direction: column; gap: var(--s-2); }
.alt { display: flex; align-items: center; gap: var(--s-3); }
.lbl { font-size: var(--fs-xs); color: var(--text-3); text-transform: uppercase; letter-spacing: 0.06em; }
.pick { display: flex; align-items: flex-end; gap: var(--s-2); flex-wrap: wrap; }
.research summary { cursor: pointer; color: var(--text-2); }
</style>
