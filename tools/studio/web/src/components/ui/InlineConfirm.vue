<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import Btn from './Btn.vue'

/** Replaces a modal confirm. The slot must state the consequence ("55 lines move; the slot is removed"). Enter confirms, Esc cancels. */
withDefaults(defineProps<{ confirmLabel?: string; cancelLabel?: string }>(), { confirmLabel: 'Confirm', cancelLabel: 'Cancel' })
const emit = defineEmits<{ confirm: []; cancel: [] }>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
  else if (e.key === 'Enter' && !(e.target as HTMLElement | null)?.closest?.('button, a, textarea')) emit('confirm')
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="inline-confirm" role="alertdialog" aria-live="assertive">
    <span><slot /></span>
    <span class="acts">
      <Btn size="sm" variant="primary" kbd="↵" @click="emit('confirm')">{{ confirmLabel }}</Btn>
      <Btn size="sm" variant="ghost" kbd="Esc" @click="emit('cancel')">{{ cancelLabel }}</Btn>
    </span>
  </div>
</template>

<style scoped>
.inline-confirm { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); padding: 10px 12px; border-radius: var(--r-md); background: var(--warn-tint); border: 1px solid var(--warn-line); font-size: 13px; }
.acts { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-left: auto; align-items: center; }
</style>
