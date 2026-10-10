<script setup lang="ts">
import Icon from './Icon.vue'
import Kbd from './Kbd.vue'

export type Verdict = 'good' | 'bad' | null
/** The 64px Good / Bad pair. Clicking the active one clears it. The G / B keys are the page's to bind (see useQaKeys). */
const props = defineProps<{ modelValue: Verdict; hints?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: Verdict] }>()
const pick = (v: 'good' | 'bad') => emit('update:modelValue', props.modelValue === v ? null : v)
</script>

<template>
  <div class="judge" role="group" aria-label="Verdict">
    <button type="button" class="j good" :class="{ on: modelValue === 'good' }" :aria-pressed="modelValue === 'good'" @click="pick('good')"><Icon name="check" :size="18" />Good<Kbd v-if="hints !== false">G</Kbd></button>
    <button type="button" class="j bad" :class="{ on: modelValue === 'bad' }" :aria-pressed="modelValue === 'bad'" @click="pick('bad')"><Icon name="x" :size="18" />Bad<Kbd v-if="hints !== false">B</Kbd></button>
  </div>
</template>

<style scoped>
.judge { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-3); }
.j { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: var(--hit-xl); font-size: 17px; font-weight: 600; border: 1.5px solid; border-radius: var(--r-lg); cursor: pointer; padding: 0 var(--s-3); }
.good { color: var(--good); border-color: var(--good-line); background: var(--good-tint); }
.bad { color: var(--bad); border-color: var(--bad-line); background: var(--bad-tint); }
.good.on { background: var(--good); color: var(--good-ink); border-color: var(--good); }
.bad.on { background: var(--bad); color: var(--bad-ink); border-color: var(--bad); }
@media (max-width: 640px) { .j { min-height: 56px; } }
</style>
