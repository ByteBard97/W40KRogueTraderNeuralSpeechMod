<script setup lang="ts">
import type { RegisterPreview } from '../../api/types'
import InlineConfirm from '../ui/InlineConfirm.vue'

defineProps<{ preview: RegisterPreview }>()
const emit = defineEmits<{ confirm: []; cancel: [] }>()
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`
</script>

<template>
  <div class="register-panel" data-register-panel>
    <InlineConfirm confirm-label="Register" @confirm="emit('confirm')" @cancel="emit('cancel')">
      This writes the prompt bank: <b>{{ plural(preview.counts.add, 'voice') }}</b> added, <b>{{ preview.counts.update }}</b> changed,
      <b>{{ preview.counts.unchanged }}</b> already there, <b>{{ preview.counts.skipped }}</b> skipped ({{ preview.counts.processed }} processed, rendered at 20 steps).
      prompts.json is backed up first and no render starts.
    </InlineConfirm>
    <details v-if="preview.skipped.length" class="skipped" open>
      <summary>Skipped ({{ preview.skipped.length }})</summary>
      <ul>
        <li v-for="s in preview.skipped" :key="s.key"><span class="mono">{{ s.key }}</span> <span class="why">{{ s.reason }}</span></li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.register-panel { display: flex; flex-direction: column; gap: var(--s-2); }
.skipped { font-size: 13px; color: var(--text-2); }
summary { cursor: pointer; }
ul { margin: var(--s-1) 0 0; padding-left: var(--s-4); max-height: 220px; overflow: auto; }
.why { color: var(--text-3); }
</style>
