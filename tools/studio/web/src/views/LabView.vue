<script setup lang="ts">
import { onMounted } from 'vue'
import LabLines from '../components/lab/LabLines.vue'
import LabPipeline from '../components/lab/LabPipeline.vue'
import LabRecipe from '../components/lab/LabRecipe.vue'
import LabActions from '../components/lab/LabActions.vue'
import LabTakes from '../components/lab/LabTakes.vue'
import LabWordTest from '../components/lab/LabWordTest.vue'
import InlineError from '../components/ui/InlineError.vue'
import { useLabPrepare } from '../composables/useLabPrepare'
import { useLabRender } from '../composables/useLabRender'
import { useLabStore } from '../stores/lab'

const lab = useLabStore()
const render = useLabRender()
useLabPrepare()
onMounted(() => void lab.init())
</script>

<template>
  <div class="page lab">
    <header class="page-head">
      <h1 class="page-title">Render Lab</h1>
      <span class="page-sub">{{ lab.speaker }} · try a recipe on the live model, listen, compare with the current render</span>
    </header>
    <InlineError v-if="lab.error" title="Something went wrong"><div data-error>{{ lab.error }}</div></InlineError>
    <div class="cols">
      <LabLines />
      <div class="mid">
        <LabRecipe :seed-count="render.seedCount.value" @update:seed-count="render.setSeedCount" />
        <LabActions :job="render.job.value" :running="render.running.value" :percent="render.percent.value" :error="render.error.value" @render-selected="render.renderSelected()" @render-checked="render.renderChecked()" @cancel="render.cancel()" />
      </div>
      <LabPipeline />
    </div>
    <LabTakes />
    <LabWordTest />
  </div>
</template>

<style scoped>
.mid { display: flex; flex-direction: column; gap: var(--s-3); min-width: 0; }
.cols { display: grid; grid-template-columns: minmax(280px, 340px) minmax(0, 1fr) minmax(280px, 380px); gap: var(--s-4); align-items: start; }
@media (max-width: 1100px) { .cols { grid-template-columns: minmax(0, 1fr); } }
</style>
