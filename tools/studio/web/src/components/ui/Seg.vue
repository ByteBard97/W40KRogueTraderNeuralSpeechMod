<script setup lang="ts" generic="T extends string | number">
export interface SegOption<V> { value: V; label: string; disabled?: boolean }

defineProps<{ options: SegOption<T>[]; modelValue: T; ariaLabel: string; accent?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <div class="seg" :class="{ accent }" role="group" :aria-label="ariaLabel">
    <button
      v-for="o in options"
      :key="String(o.value)"
      type="button"
      :aria-pressed="o.value === modelValue"
      :disabled="o.disabled"
      @click="emit('update:modelValue', o.value)"
    >
      {{ o.label }}
    </button>
  </div>
</template>

<style scoped>
.seg { display: inline-flex; padding: 2px; gap: 2px; border-radius: var(--r-md); background: var(--n-1); border: 1px solid var(--line-strong); }
button { min-height: 26px; padding: 0 10px; border: 0; border-radius: var(--r-sm); background: transparent; color: var(--text-2); font-size: var(--fs-sm); font-weight: 500; cursor: pointer; white-space: nowrap; }
button:hover { color: var(--text); background: var(--hover); }
button:disabled { color: var(--text-off); cursor: not-allowed; background: transparent; opacity: 1; }
button[aria-pressed="true"] { background: var(--inset); color: var(--text); box-shadow: inset 0 0 0 1px var(--line-strong); }
.accent button[aria-pressed="true"] { background: var(--accent-tint); color: var(--accent-hi); box-shadow: inset 0 0 0 1px var(--selected-line); }
</style>
