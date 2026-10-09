<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { FxLabels } from '../../api/types'

const LABELS = ['machine', 'vox_channel', 'helmet', 'ethereal', 'monstrous', 'cavernous']
const props = defineProps<{ labels: FxLabels; presets: string[] }>()
const emit = defineEmits<{ save: [labels: FxLabels] }>()
const draft = reactive<FxLabels>({})

const snapshot = (src: FxLabels) => JSON.stringify(LABELS.map((k) => src[k] ?? []))
let seeded = ''

/** Reseed from the saved labels only when the draft has no unsaved edits (or already equals them). */
watch(
  () => props.labels,
  (l) => {
    const incoming = snapshot(l)
    if (seeded && snapshot(draft) !== seeded && snapshot(draft) !== incoming) return
    for (const k of LABELS) draft[k] = [...(l[k] ?? [])]
    seeded = incoming
  },
  { immediate: true, deep: true },
)

const add = (label: string, name: string) => name && !draft[label].includes(name) && draft[label].push(name)
const remove = (label: string, i: number) => draft[label].splice(i, 1)
function move(label: string, i: number, to: number) {
  if (to < 0 || to >= draft[label].length) return
  const [x] = draft[label].splice(i, 1)
  draft[label].splice(to, 0, x)
}
</script>

<template>
  <div>
    <div v-for="label in LABELS" :key="label" class="label">
      <b class="name">{{ label }}</b>
      <span v-for="(p, i) in draft[label]" :key="p" class="chain">
        {{ p }}
        <button data-up :disabled="i === 0" @click="move(label, i, i - 1)">←</button>
        <button data-down :disabled="i === draft[label].length - 1" @click="move(label, i, i + 1)">→</button>
        <button data-remove @click="remove(label, i)">×</button>
      </span>
      <select data-add @change="add(label, ($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).value = ''">
        <option value="">add preset…</option>
        <option v-for="p in presets" :key="p" :value="p">{{ p }}</option>
      </select>
    </div>
    <button data-save class="primary" @click="emit('save', { ...draft })">Save label map</button>
  </div>
</template>

<style scoped>
.label { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 4px 0; border-top: 1px solid var(--line); }
.name { min-width: 110px; }
select[data-add] { max-width: 100%; }
.chain { border: 1px solid var(--line); border-radius: 6px; padding: 1px 4px; font-size: 12px; }
.primary { background: var(--acc); color: var(--on-acc); border-color: var(--acc); margin-top: 6px; }
</style>
