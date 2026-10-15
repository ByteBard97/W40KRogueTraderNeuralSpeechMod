<script setup lang="ts">
import { computed } from 'vue'
import type { LabJob } from '../../api/labTypes'
import { useLabStore } from '../../stores/lab'
import { useModelStore } from '../../stores/model'
import Btn from '../ui/Btn.vue'
import InlineError from '../ui/InlineError.vue'

const props = defineProps<{ job: LabJob | null; running: boolean; percent: number; error: string | null }>()
const emit = defineEmits<{ renderSelected: []; renderChecked: []; cancel: [] }>()
const lab = useLabStore()
const model = useModelStore()
const down = computed(() => model.state === 'down')
const blocked = computed(() => down.value || props.running)
</script>

<template>
  <div class="bar">
    <InlineError v-if="down" title="The model is not running"><div data-model-down>{{ model.reason }} Rendering is disabled until it is back.</div></InlineError>
    <div class="row">
      <Btn variant="primary" data-render-selected :disabled="blocked || !lab.selectedGuid" @click="emit('renderSelected')">Render selected line</Btn>
      <Btn data-render-checked :disabled="blocked || !lab.checked.length" @click="emit('renderChecked')">Render checked lines ({{ lab.checked.length }})</Btn>
      <span v-if="job" class="prog" data-progress>
        <progress :value="job.done" :max="job.total || 1" :aria-label="`${percent}% rendered`" />
        <span class="num">{{ job.done }}/{{ job.total }}</span>
        <span class="muted">{{ job.state }}</span>
        <Btn v-if="running" size="sm" variant="danger" data-cancel @click="emit('cancel')">Cancel</Btn>
      </span>
    </div>
    <InlineError v-if="error" title="Render problem"><div data-render-error>{{ error }}</div></InlineError>
  </div>
</template>

<style scoped>
.bar { display: flex; flex-direction: column; gap: var(--s-2); }
.row { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.prog { display: inline-flex; gap: var(--s-2); align-items: center; }
progress { width: 160px; accent-color: var(--accent); }
</style>
