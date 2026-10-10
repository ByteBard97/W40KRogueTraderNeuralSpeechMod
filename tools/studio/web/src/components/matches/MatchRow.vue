<script setup lang="ts">
import { computed } from 'vue'
import type { MatchRowData } from '../../api/types'
import { decisionLabel, entryName, plural } from '../../utils/matchText'
import StatusDot from '../ui/StatusDot.vue'

/** One line of the review queue: who, proposed speaker, state, and where it came from. */
const props = defineProps<{ row: MatchRowData; selected: boolean }>()
defineEmits<{ select: [] }>()

const dot = computed(() => (props.row.decision === 'accept' ? 'good' : props.row.decision === 'reject' ? 'bad' : props.row.flagged ? 'flag' : 'idle'))
const dotLabel = computed(() => (props.row.decision ? decisionLabel(props.row) : props.row.flagged ? 'Flagged, not reviewed' : 'Not reviewed'))
</script>

<template>
  <button type="button" class="q-row" :class="{ sel: selected }" :aria-current="selected ? 'true' : undefined" @click="$emit('select')">
    <StatusDot :status="dot" :label="dotLabel" />
    <span class="who"><b>{{ entryName(row) }}</b> → {{ row.speaker }}</span>
    <span class="dec" :class="{ acc: row.decision === 'accept', rej: row.decision === 'reject' }">{{ decisionLabel(row) }}</span>
    <span class="src">{{ row.conversation }} · {{ plural(row.lines, 'line') }}</span>
  </button>
</template>

<style scoped>
.q-row { display: grid; grid-template-columns: 14px minmax(0, 1fr) auto; gap: 4px var(--s-3); align-items: center; width: 100%; min-height: 52px; padding: var(--s-2) 10px; border: 0; border-top: 1px solid var(--line); background: transparent; color: inherit; text-align: left; cursor: pointer; font: inherit; }
.q-row:hover { background: var(--hover); }
.q-row.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); border-top-color: transparent; }
.who { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.who b { color: var(--text); }
.src { grid-column: 2 / 4; font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dec { font-size: var(--fs-xs); font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); }
.dec.acc { color: var(--good); font-weight: 600; }
.dec.rej { color: var(--bad); font-weight: 600; }
</style>
