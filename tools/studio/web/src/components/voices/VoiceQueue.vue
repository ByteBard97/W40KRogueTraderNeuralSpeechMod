<script setup lang="ts">
import type { Bg3Voice, LabelDef } from '../../api/types'
import { labelSummary, requiredDone } from '../../utils/castVoices'
import StatusDot from '../ui/StatusDot.vue'

/** The BG3 voices to label: a dot for "fully labelled", and what has been set so far. */
defineProps<{ rows: Bg3Voice[]; selected: string | null; schema: LabelDef[] }>()
defineEmits<{ select: [slug: string] }>()
const required = (s: LabelDef[]) => s.filter((d) => d.required).length
</script>

<template>
  <ul class="queue" aria-label="BG3 voices">
    <li v-for="v in rows" :key="v.slug">
      <button type="button" class="row" :class="{ sel: v.slug === selected }" :aria-current="v.slug === selected ? 'true' : undefined" @click="$emit('select', v.slug)">
        <StatusDot :status="v.complete ? 'good' : 'idle'" :label="v.complete ? 'Fully labelled' : 'Not fully labelled'" />
        <span class="who"><b>{{ v.name }}</b><span class="meta">{{ v.lines.toLocaleString() }} lines<template v-if="labelSummary(v)"> · {{ labelSummary(v) }}</template></span></span>
        <span class="n">{{ requiredDone(v, schema) }}/{{ required(schema) }}</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.queue { list-style: none; margin: 0; padding: 0; }
.row { display: grid; grid-template-columns: 14px minmax(0, 1fr) auto; gap: var(--s-3); align-items: center; width: 100%; min-height: 48px; padding: var(--s-2) 10px; border: 0; border-top: 1px solid var(--line); background: transparent; color: inherit; text-align: left; cursor: pointer; font: inherit; }
.row:hover { background: var(--hover); }
.row.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); border-top-color: transparent; }
.who { display: flex; flex-direction: column; min-width: 0; }
.who b { color: var(--text); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.n { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); }
</style>
