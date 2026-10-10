<script setup lang="ts">
export interface ChipOption { value: string; label: string; count?: number }

/** Toggle chips. Single choice by default (click the active chip again to clear when `clearable`); `multiple` keeps a set. */
const props = defineProps<{ options: ChipOption[]; modelValue: string | string[] | null; multiple?: boolean; clearable?: boolean; ariaLabel?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string | string[] | null] }>()

const isOn = (v: string) => (Array.isArray(props.modelValue) ? props.modelValue.includes(v) : props.modelValue === v)

function toggle(v: string) {
  if (props.multiple) {
    const cur = Array.isArray(props.modelValue) ? props.modelValue : []
    emit('update:modelValue', cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v])
  } else {
    emit('update:modelValue', props.clearable && props.modelValue === v ? null : v)
  }
}
</script>

<template>
  <div class="chips" role="group" :aria-label="ariaLabel">
    <button v-for="o in options" :key="o.value" type="button" class="chip" :aria-pressed="isOn(o.value)" @click="toggle(o.value)">
      {{ o.label }}<span v-if="o.count !== undefined" class="n">{{ o.count }}</span>
    </button>
  </div>
</template>

<style scoped>
.chips { display: flex; flex-wrap: wrap; gap: var(--s-2); }
.chip { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 0 10px; border-radius: var(--r-pill); border: 1px solid var(--line-strong); background: transparent; color: var(--text-2); font-size: var(--fs-sm); cursor: pointer; white-space: nowrap; }
.chip:hover { color: var(--text); border-color: var(--n-6); }
.chip[aria-pressed="true"] { background: var(--accent-tint); color: var(--accent-hi); border-color: var(--selected-line); }
.n { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); }
.chip[aria-pressed="true"] .n { color: var(--accent); }
</style>
