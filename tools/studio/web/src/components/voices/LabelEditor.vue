<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Bg3Voice, LabelDef, LabelValue } from '../../api/types'

/** All labels of one voice. A dashed chip is the automatic guess: click it to confirm. Click a set chip again to clear it. */
const props = defineProps<{ voice: Bg3Voice; schema: LabelDef[] }>()
const emit = defineEmits<{ set: [key: string, value: LabelValue | null] }>()

const note = ref(String(props.voice.mine.note ?? ''))
watch(() => props.voice.slug, () => { note.value = String(props.voice.mine.note ?? '') })

const mineOf = (key: string) => props.voice.mine[key]
const isMine = (d: LabelDef, o: string) => (Array.isArray(mineOf(d.key)) ? (mineOf(d.key) as string[]).includes(o) : mineOf(d.key) === o)
const isGuess = (d: LabelDef, o: string) => mineOf(d.key) === undefined && props.voice.labels[d.key] === o
const hint = (d: LabelDef) => (d.allow_several && d.kind === 'single' ? 'Pick more than one if the voice sits between' : '')
const stars = (d: LabelDef) => Number(mineOf(d.key) ?? 0)

const several = (d: LabelDef) => d.kind === 'multi' || !!d.allow_several

function pick(d: LabelDef, o: string) {
  if (several(d)) {
    const mine = mineOf(d.key)
    const cur = Array.isArray(mine) ? mine : mine ? [mine] : []
    const next = cur.includes(o) ? cur.filter((x) => x !== o) : [...cur, o]
    emit('set', d.key, next.length > 1 || d.kind === 'multi' ? next : next[0] ?? null)    // a single pick is saved as a plain value
  } else {
    emit('set', d.key, isMine(d, o) ? null : o)
  }
}
</script>

<template>
  <div class="le">
    <div v-for="d in schema" :key="d.key" class="row" :class="{ req: d.required }">
      <span class="name" :title="hint(d)">{{ d.label }}<i v-if="d.required && mineOf(d.key) === undefined" class="need" title="Not set yet"> •</i></span>
      <div v-if="d.kind === 'text'" class="note">
        <input v-model="note" type="text" maxlength="500" placeholder="Anything worth remembering about this voice" :aria-label="d.label" @blur="emit('set', d.key, note.trim() || null)" @keydown.enter="($event.target as HTMLInputElement).blur()" />
      </div>
      <div v-else-if="d.kind === 'rating'" class="chips">
        <button v-for="o in d.options" :key="o" type="button" class="star" :class="{ lit: Number(o) <= stars(d) }" :aria-label="`${o} of 5`" :aria-pressed="stars(d) === Number(o)" @click="pick(d, o)">★</button>
      </div>
      <div v-else class="chips">
        <button v-for="o in d.options" :key="o" type="button" class="chip" :class="{ guess: isGuess(d, o) }" :aria-pressed="isMine(d, o)" @click="pick(d, o)">{{ o }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.le { display: flex; flex-direction: column; gap: var(--s-2); }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); }
.name { width: 92px; flex: none; color: var(--text-3); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.05em; }
.row.req .name { color: var(--text-2); }
.need { color: var(--accent); font-style: normal; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip { min-height: 28px; padding: 0 12px; border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--n-1); color: var(--text-2); cursor: pointer; font-size: var(--fs-md); }
.chip:hover { background: var(--hover); }
.chip.guess { border-style: dashed; color: var(--text-3); }
.chip[aria-pressed="true"] { background: var(--accent-tint); border-color: var(--accent); color: var(--accent-hi); font-weight: 600; }
.star { background: none; border: 0; font-size: 20px; color: var(--n-5); cursor: pointer; padding: 0 2px; }
.star.lit { color: var(--accent); }
.note { flex: 1 1 260px; }
.note input { width: 100%; min-height: 30px; background: var(--inset); color: var(--text); border: 1px solid var(--line-strong); border-radius: var(--r-md); padding: 0 var(--s-2); }
</style>
