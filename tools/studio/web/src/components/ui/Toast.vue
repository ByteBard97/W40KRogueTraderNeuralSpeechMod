<script setup lang="ts">
import Btn from './Btn.vue'
import Icon from './Icon.vue'

/** Presentational toast (the stack renders these from useToasts; use this directly for static examples). */
defineProps<{ kind?: 'ok' | 'err'; actionLabel?: string; actionKey?: string }>()
const emit = defineEmits<{ action: [] }>()
</script>

<template>
  <div class="toast" :class="{ err: kind === 'err' }" :role="kind === 'err' ? 'alert' : 'status'">
    <Icon class="ico" :name="kind === 'err' ? 'warn' : 'check'" />
    <span><slot /></span>
    <Btn v-if="actionLabel" size="sm" :kbd="actionKey" class="act" @click="emit('action')">{{ actionLabel }}</Btn>
  </div>
</template>

<style scoped>
.toast { display: flex; align-items: center; gap: var(--s-3); padding: 10px 12px 10px 14px; border-radius: var(--r-lg); background: var(--n-3); border: 1px solid var(--line-strong); box-shadow: var(--e-2); color: var(--text); font-size: 13px; max-width: 460px; }
.ico { color: var(--good); flex: none; }
.err .ico { color: var(--bad); }
.act { margin-left: auto; }
</style>
