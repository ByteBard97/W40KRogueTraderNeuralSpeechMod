<script setup lang="ts">
import { computed } from 'vue'
import type { LabMetrics } from '../../api/labTypes'
import { flagTone } from '../../utils/labRecipe'

/** Crest factor in dB, coloured by the auto flag: red overdriven (or crest under 11), amber clipped. */
const props = defineProps<{ metrics: Pick<LabMetrics, 'flag' | 'crest_db'> | null }>()
const tone = computed(() => flagTone(props.metrics))
const text = computed(() => (props.metrics?.crest_db == null ? '–' : `${props.metrics.crest_db.toFixed(1)} dB`))
const title = computed(() => (props.metrics?.flag ? `crest ${text.value}, ${props.metrics.flag}` : `crest ${text.value}`))
</script>

<template>
  <span class="badge num" :class="`t-${tone}`" :title="title" data-crest>{{ text }}<template v-if="metrics?.flag"> · {{ metrics.flag }}</template></span>
</template>

<style scoped>
.badge { display: inline-flex; align-items: center; height: 20px; padding: 0 6px; border-radius: var(--r-sm); border: 1px solid var(--line); font-size: var(--fs-xs); color: var(--text-3); white-space: nowrap; }
.t-ok { color: var(--good); border-color: var(--good-line); }
.t-warn { color: var(--warn); border-color: var(--warn-line); background: var(--warn-tint); }
.t-bad { color: var(--bad); border-color: var(--bad-line); background: var(--bad-tint); }
</style>
