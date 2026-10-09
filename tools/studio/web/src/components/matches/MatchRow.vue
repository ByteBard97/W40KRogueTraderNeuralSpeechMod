<script setup lang="ts">
import type { MatchRowData, MatchValue } from '../../api/types'

defineProps<{ row: MatchRowData }>()
const emit = defineEmits<{ decide: [value: MatchValue] }>()
</script>

<template>
  <div class="row" :class="{ flag: row.flagged }">
    <div class="head">
      <select :value="row.effective" data-decision @change="emit('decide', ($event.target as HTMLSelectElement).value as MatchValue)">
        <option value="">undecided</option>
        <option value="accept">accept</option>
        <option value="reject">reject</option>
      </select>
      <b>{{ row.name ?? row.label ?? row.entry }}</b>
      <i class="dim">({{ row.label }}, {{ row.gender ?? '?' }}, {{ row.species ?? '?' }})</i>
      <span>→</span>
      <b class="sp">{{ row.speaker }}</b>
      <span class="chip" :class="row.has_bank ? 'bank' : 'nobank'">{{ row.has_bank ? 'bank' : 'no bank' }}</span>
      <span class="dim">game gender {{ row.game_gender ?? '?' }}, {{ row.speaker_lines }} lines</span>
    </div>
    <div class="dim">{{ row.conversation }} · {{ row.lines }} lines<template v-if="row.role"> · {{ row.role }}</template></div>
    <div v-if="row.warning" class="warn">{{ row.warning }}</div>
    <div v-if="row.ambiguous_with?.length" class="warn">also matches: {{ row.ambiguous_with.join(', ') }}</div>
    <div v-if="row.evidence.length" class="dim">evidence: {{ row.evidence.join('; ') }}</div>
    <template v-for="(s, i) in row.samples" :key="i">
      <div v-if="i && row.gaps[i - 1]" class="dim sample">… (other speakers' lines in between)</div>
      <div v-if="s" class="sample">{{ s }}</div>
    </template>
  </div>
</template>

<style scoped>
.row { border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; margin: 6px 0; background: var(--card); }
.row.flag { border-color: var(--warn); }
.head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.sp { color: var(--acc); }
.chip { border-radius: 10px; padding: 0 7px; font-size: 11px; border: 1px solid var(--line); }
.chip.bank { color: var(--ok); }
.chip.nobank { color: var(--dim); }
.sample { margin: 2px 0 0 12px; color: var(--dim); font-size: 13px; }
.dim { color: var(--dim); font-size: 12px; }
.warn { color: var(--warn); font-size: 13px; }
</style>
