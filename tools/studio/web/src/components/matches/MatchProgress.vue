<script setup lang="ts">
import { computed } from 'vue'
import type { MatchCounts } from '../../api/types'
import SavedIndicator from '../ui/SavedIndicator.vue'

/** Reviewed N / total with accepted and rejected as two parts of one bar. Explicit decisions only. */
const props = defineProps<{ counts: MatchCounts | null; saved?: boolean; note?: string }>()
const PERCENT = 100
const known = computed(() => props.counts?.total !== undefined && props.counts.reviewed !== undefined)
const total = computed(() => props.counts?.total ?? 0)
const pct = (n: number | undefined) => (total.value ? ((n ?? 0) / total.value) * PERCENT : 0)
const fmt = (n: number | undefined) => (n ?? 0).toLocaleString('en-US')
</script>

<template>
  <div v-if="known" class="progress" role="group" aria-label="Review progress">
    <div class="label"><span>Reviewed</span><span class="num">{{ fmt(counts?.reviewed) }} / {{ fmt(total) }}</span></div>
    <div class="bar" role="progressbar" aria-label="Reviewed" :aria-valuenow="counts?.reviewed" aria-valuemin="0" :aria-valuemax="total">
      <i class="g" :style="{ width: `${pct(counts?.accepted)}%` }" /><i class="b" :style="{ width: `${pct(counts?.rejected)}%` }" />
    </div>
    <div class="tally"><span>accepted {{ fmt(counts?.accepted) }}</span><span>rejected {{ fmt(counts?.rejected) }}</span><SavedIndicator v-if="saved" :ago="note || undefined" /><span v-else>saved as you go · Pools updates</span></div>
  </div>
</template>

<style scoped>
.progress { display: flex; flex-direction: column; gap: 6px; min-width: 200px; }
.label { display: flex; justify-content: space-between; gap: var(--s-3); font-size: var(--fs-sm); color: var(--text-2); }
.bar { height: 6px; border-radius: 3px; background: var(--n-4); overflow: hidden; display: flex; }
.bar i { display: block; height: 100%; }
.g { background: var(--good); }
.b { background: var(--bad); }
.tally { display: flex; flex-wrap: wrap; gap: var(--s-1) var(--s-3); font-size: var(--fs-sm); color: var(--text-3); }
</style>
