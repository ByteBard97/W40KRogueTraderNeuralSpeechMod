<script setup lang="ts">
import Icon from '../ui/Icon.vue'

const STARS = [1, 2, 3, 4, 5]
/** 1-5 stars. Clicking the star that is already the value clears it (emits 0). `label` names the group ("Fit", "Accent", "Take rating"). */
const props = defineProps<{ modelValue: number; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
const click = (n: number) => emit('update:modelValue', props.modelValue === n ? 0 : n)
</script>

<template>
  <div class="stars" role="group" :aria-label="`${label}, ${modelValue ? `${modelValue} of 5` : 'not rated'}`">
    <button v-for="n in STARS" :key="n" type="button" :class="{ on: modelValue >= n }" :aria-label="`${label} ${n}`" :aria-pressed="modelValue === n" @click="click(n)">
      <Icon name="star" :size="14" />
    </button>
  </div>
</template>

<style scoped>
.stars { display: inline-flex; }
button { width: 22px; height: var(--hit); padding: 0; border: 0; background: transparent; color: var(--n-5); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
button:hover { color: var(--warn); }
button.on { color: var(--accent); }
</style>
