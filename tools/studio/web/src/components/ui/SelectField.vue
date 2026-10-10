<script setup lang="ts">
export interface SelectOption { value: string; label: string }
defineProps<{ label: string; options: SelectOption[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <label class="field">
    <span class="lbl">{{ label }}</span>
    <select :value="modelValue" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)">
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </label>
</template>
