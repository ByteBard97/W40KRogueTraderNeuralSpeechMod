<script setup lang="ts">
const STARS = [1, 2, 3, 4, 5]
const props = defineProps<{ modelValue: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
const click = (n: number) => emit('update:modelValue', props.modelValue === n ? 0 : n)
</script>

<template>
  <span class="stars">
    <button v-for="n in STARS" :key="n" class="star" :class="{ on: modelValue >= n }" :aria-label="`${n} stars`" @click="click(n)">★</button>
  </span>
</template>

<style scoped>
.star { background: none; border: 0; padding: 0 1px; color: var(--dim); font-size: 16px; cursor: pointer; }
.star.on { color: var(--warn); }
</style>
