<script setup lang="ts">
import type { AssignmentItem } from '../../api/types'
import StatusDot from '../ui/StatusDot.vue'

/** The characters and groups, biggest first: a dot for "has a voice", who they are, and the voice they got. */
defineProps<{ rows: AssignmentItem[]; selected: string | null }>()
defineEmits<{ select: [key: string] }>()
const dot = (i: AssignmentItem) => (i.status !== 'assigned' ? 'flag' : i.owner ? 'good' : 'idle')
const dotLabel = (i: AssignmentItem) => (i.status !== 'assigned' ? 'Needs more information' : i.owner ? 'Picked by you' : 'Chosen by the rules')
const who = (i: AssignmentItem) => [i.gender, i.species, i.role].filter(Boolean).join(' · ')
</script>

<template>
  <ul class="queue" aria-label="Characters and groups">
    <li v-for="i in rows" :key="i.key">
      <button type="button" class="row" :class="{ sel: i.key === selected }" :aria-current="i.key === selected ? 'true' : undefined" @click="$emit('select', i.key)">
        <StatusDot :status="dot(i)" :label="dotLabel(i)" />
        <span class="who"><b>{{ i.name }}</b><span class="meta">{{ i.lines }} lines · {{ who(i) }}</span></span>
        <span v-if="i.voice_name" class="voice" :class="{ mine: i.owner }">{{ i.voice_name }}</span>
        <span v-else class="voice none">needs info</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.queue { list-style: none; margin: 0; padding: 0; }
.row { display: grid; grid-template-columns: 14px minmax(0, 1fr) auto; gap: 2px var(--s-3); align-items: center; width: 100%; min-height: 52px; padding: var(--s-2) 10px; border: 0; border-top: 1px solid var(--line); background: transparent; color: inherit; text-align: left; cursor: pointer; font: inherit; }
.row:hover { background: var(--hover); }
.row.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); border-top-color: transparent; }
.who { display: flex; flex-direction: column; min-width: 0; }
.who b { color: var(--text); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.voice { font-size: var(--fs-xs); color: var(--accent-hi); font-weight: 600; max-width: 140px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.voice.mine { color: var(--good); }
.voice.none { color: var(--warn); }
</style>
