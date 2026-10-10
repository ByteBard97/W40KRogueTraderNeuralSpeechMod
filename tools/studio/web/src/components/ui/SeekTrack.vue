<script setup lang="ts">
import { computed } from 'vue'

const STEPS = 1000
/** Seek / volume track. A transparent range input sits over the drawn bar, so mouse, touch and arrow keys all work natively. */
const props = defineProps<{ modelValue: number; label: string; disabled?: boolean; valueText?: string }>()
const emit = defineEmits<{ 'update:modelValue': [fraction: number] }>()
const pct = computed(() => `${Math.min(Math.max(props.modelValue, 0), 1) * 100}%`)
</script>

<template>
  <div class="track">
    <div class="fill" :style="{ width: pct }" />
    <div class="knob" :style="{ left: pct }" />
    <input
      class="hit"
      type="range"
      min="0"
      :max="STEPS"
      :value="Math.round(modelValue * STEPS)"
      :aria-label="label"
      :aria-valuetext="valueText"
      :disabled="disabled"
      @input="emit('update:modelValue', Number(($event.target as HTMLInputElement).value) / STEPS)"
    />
  </div>
</template>

<style scoped>
.track { position: relative; flex: 1 1 auto; height: 6px; border-radius: 3px; background: var(--n-4); min-width: 40px; }
.fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 3px; background: var(--accent); }
.knob { position: absolute; top: 50%; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%; background: var(--accent-hi); box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.4); pointer-events: none; }
.hit { position: absolute; left: -7px; right: -7px; top: -9px; bottom: -9px; width: calc(100% + 14px); height: 24px; margin: 0; opacity: 0; cursor: pointer; padding: 0; border: 0; }
.track:focus-within { outline: 2px solid var(--focus); outline-offset: 6px; }
</style>
