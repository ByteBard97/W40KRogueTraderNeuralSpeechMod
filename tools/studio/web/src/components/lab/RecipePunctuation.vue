<script setup lang="ts">
import { computed } from 'vue'
import { useLabStore } from '../../stores/lab'

const lab = useLabStore()
const r = computed(() => lab.recipe!)
const marks = computed(() => lab.options?.marks ?? [])
const actions = computed(() => lab.options?.actions ?? [])
const label = (m: string) => m.replace(/_/g, ' ')
</script>

<template>
  <div class="punct">
    <label v-for="m in marks" :key="m" class="field" data-mark>
      <span class="lbl">{{ label(m) }}</span>
      <select v-model="r.punctuation[m]" :aria-label="`${label(m)} action`">
        <option v-for="a in actions" :key="a" :value="a">{{ a }}</option>
      </select>
    </label>
    <label class="field"><span class="lbl">pause ms</span><input v-model.number="r.pause_ms" class="num" type="number" min="0" step="10" aria-label="pause ms" data-pause-ms /></label>
  </div>
  <p class="muted hint">"pause" cuts the text at the mark and plays that much silence between the two renders.</p>
</template>

<style scoped>
.punct { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: var(--s-2); }
.hint { font-size: var(--fs-sm); margin: var(--s-2) 0 0; }
.field select { background: transparent; }
</style>
