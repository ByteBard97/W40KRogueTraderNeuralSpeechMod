<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { isTypingTarget } from '../../utils/keys'
import Icon from './Icon.vue'
import Kbd from './Kbd.vue'

const FOCUS_KEY = '/'
const props = withDefaults(defineProps<{ modelValue: string; placeholder?: string; label?: string; focusKey?: boolean }>(), {
  placeholder: 'Search',
  label: 'Search',
  focusKey: true,
})
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const input = ref<HTMLInputElement | null>(null)

function onKey(e: KeyboardEvent) {
  if (e.key !== FOCUS_KEY || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || isTypingTarget(e.target)) return
  e.preventDefault()
  input.value?.focus()
  input.value?.select()
}
onMounted(() => props.focusKey && document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <label class="field">
    <Icon name="search" :size="14" />
    <span class="vh">{{ label }}</span>
    <input ref="input" type="search" :value="modelValue" :placeholder="placeholder" @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
    <Kbd v-if="focusKey" class="hide-sm">/</Kbd>
  </label>
</template>
