<script setup lang="ts">
import { computed } from 'vue'
import type { LabJob } from '../../api/labTypes'
import { useLabStore } from '../../stores/lab'
import InlinePlay from '../ui/InlinePlay.vue'
import CrestBadge from './CrestBadge.vue'
import LabRenderBar from './LabRenderBar.vue'
import OpusCheck from './OpusCheck.vue'

/** Under the settings: render the selected line, and listen to the original next to the newest take of that line. */
defineProps<{ job: LabJob | null; running: boolean; percent: number; error: string | null }>()
const emit = defineEmits<{ renderSelected: []; renderChecked: []; cancel: [] }>()
const lab = useLabStore()
const original = computed(() => lab.selected?.current ?? null)
const latest = computed(() => lab.takes[0] ?? null)
</script>

<template>
  <section class="actions vs-card" aria-label="Render and listen">
    <LabRenderBar :job="job" :running="running" :percent="percent" :error="error" @render-selected="emit('renderSelected')" @render-checked="emit('renderChecked')" @cancel="emit('cancel')" />
    <div class="listen">
      <div class="clip" data-original>
        <InlinePlay :id="original?.wav ?? null" large title="Original (current render)" :subtitle="lab.selectedGuid ?? ''" unavailable-reason="This line has no current render" />
        <div class="what"><b>Original</b><span class="muted">the render now in the game</span>
          <span v-if="original" class="m"><span class="num">{{ original.seconds?.toFixed(1) }}s</span><CrestBadge :metrics="original" /></span>
        </div>
      </div>
      <div class="clip" data-latest>
        <InlinePlay :id="latest?.wav ?? null" large title="Latest take" :subtitle="latest?.id ?? ''" unavailable-reason="Render this line to get a take" />
        <div class="what"><b>New (latest take)</b><span class="muted">{{ latest ? `seed ${latest.seed}` : 'not rendered yet' }}</span>
          <span v-if="latest" class="m"><span class="num">{{ latest.metrics.seconds.toFixed(1) }}s</span><CrestBadge :metrics="latest.metrics" /></span>
        </div>
      </div>
    </div>
    <OpusCheck />
  </section>
</template>

<style scoped>
.actions { display: flex; flex-direction: column; gap: var(--s-3); padding: var(--s-3); position: sticky; bottom: var(--s-3); z-index: 2; }
.listen { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-3); }
.clip { display: flex; gap: var(--s-3); align-items: center; min-width: 0; }
.what { display: flex; flex-direction: column; gap: 2px; min-width: 0; font-size: var(--fs-sm); }
.m { display: inline-flex; gap: var(--s-2); align-items: center; }
</style>
