<script setup lang="ts">
import { computed } from 'vue'
import { useLabStore } from '../../stores/lab'
import Seg from '../ui/Seg.vue'

const GAP_KEYS = ['sentence', 'clause', 'dash', 'ellipsis', 'paragraph']
const lab = useLabStore()
const r = computed(() => lab.recipe!)
const modes = computed(() => (lab.options?.splits ?? ['whole', 'sentence', 'clause', 'max']).map((m) => ({ value: m, label: m })))
</script>

<template>
  <div class="split-form">
    <Seg v-model="r.split.mode" :options="modes" aria-label="Split mode" />
    <div class="grid">
      <label class="field"><span class="lbl">max chars</span><input v-model.number="r.split.max_chars" class="num" type="number" min="1" data-max-chars /></label>
      <label class="field"><span class="lbl">min chars</span><input v-model.number="r.split.min_chars" class="num" type="number" min="0" data-min-chars /></label>
    </div>
    <div class="joins" data-joins>
      <label class="check"><input v-model="r.level_match" type="checkbox" data-level-match /> match loudness between pieces <span class="muted">(separately rendered sentences can differ by several dB)</span></label>
      <label class="check"><input v-model="r.trim_silence" type="checkbox" data-trim-silence /> trim silence at the edges of each piece <span class="muted">(so the gap is the gap you set)</span></label>
      <div class="grid">
        <label class="field"><span class="lbl">soften start of later pieces dB</span><input v-model.number="r.onset_soften_db" class="num" type="number" max="0" min="-24" step="1" data-soften-db /></label>
        <label class="field"><span class="lbl">soften over ms</span><input v-model.number="r.onset_soften_ms" class="num" type="number" min="10" max="1000" step="10" data-soften-ms /></label>
      </div>
    </div>
    <div class="grid" data-gaps>
      <label v-for="k in GAP_KEYS" :key="k" class="field"><span class="lbl">{{ k }} gap ms</span><input v-model.number="r.gaps_ms[k]" class="num" type="number" min="0" step="10" :aria-label="`${k} gap ms`" /></label>
    </div>
  </div>
</template>

<style scoped>
.split-form { display: flex; flex-direction: column; gap: var(--s-2); align-items: flex-start; }
.joins { display: flex; flex-direction: column; gap: var(--s-2); width: 100%; }
.check { display: flex; gap: var(--s-2); align-items: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: var(--s-2); width: 100%; }
</style>
