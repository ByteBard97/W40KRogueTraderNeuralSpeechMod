<script setup lang="ts">
import { computed } from 'vue'
import { short } from '../../pedalboard/graph'
import type { CatalogControl } from '../../pedalboard/types'
import { decimalsOf, fromT, SLIDER_STEPS, toT, wheelValue } from './controlMath'

const props = defineProps<{ nodeId: string; control: CatalogControl; value: number }>()
const emit = defineEmits<{ change: [value: number] }>()

const isToggle = computed(() => props.control.type === 'checkbox')
const testId = computed(() => `ctrl-${props.nodeId}-${short(props.control.label)}`)
const position = computed(() => Math.round(toT(props.control, props.value) * SLIDER_STEPS))
const shown = computed(() => props.value.toFixed(decimalsOf(props.control)))

function onSlide(e: Event) {
  emit('change', fromT(props.control, Number((e.target as HTMLInputElement).value) / SLIDER_STEPS))
}
function onNumber(e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  // A cleared or garbled field snaps back to the current value instead of sending NaN.
  if (Number.isFinite(v)) emit('change', v)
  else (e.target as HTMLInputElement).value = shown.value
}
function onWheel(e: WheelEvent) {
  emit('change', wheelValue(props.control, props.value, e.deltaY, e.shiftKey))
}
</script>

<template>
  <label v-if="isToggle" class="row toggle nodrag">
    <input type="checkbox" :data-testid="testId" :checked="value >= 0.5" @change="emit('change', ($event.target as HTMLInputElement).checked ? 1 : 0)" />
    <span class="name">{{ control.label }}</span>
  </label>
  <div v-else class="row nodrag nowheel" @dblclick="emit('change', control.init)" @wheel.prevent="onWheel">
    <span class="name" :title="control.label">{{ control.label }}</span>
    <input class="slide nodrag" type="range" min="0" :max="SLIDER_STEPS" step="1" :value="position" :aria-label="control.label" @input="onSlide" />
    <input
      class="num nodrag"
      type="number"
      :data-testid="testId"
      :min="control.min"
      :max="control.max"
      :step="control.step"
      :value="shown"
      :aria-label="`${control.label} value`"
      @change="onNumber"
      @dblclick.stop
    />
  </div>
</template>

<style scoped>
.row { display: grid; grid-template-columns: 1fr auto; gap: var(--s-1) var(--s-2); align-items: center; font-size: var(--fs-sm); color: var(--text-2); }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-3); }
.slide { grid-column: 1; width: 100%; accent-color: var(--accent-lo); min-width: 0; }
.num { grid-column: 2; grid-row: 1 / span 2; width: 62px; background: var(--inset); color: var(--text); border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: 2px var(--s-1); font-family: var(--font-mono); font-size: var(--fs-sm); text-align: right; }
.toggle { grid-template-columns: auto 1fr; cursor: pointer; }
.toggle input { accent-color: var(--accent-lo); }
</style>
