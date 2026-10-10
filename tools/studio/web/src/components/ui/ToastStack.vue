<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useToasts } from '../../composables/useToasts'
import { isTypingTarget } from '../../utils/keys'
import Btn from './Btn.vue'
import Icon from './Icon.vue'

/** Mount once in the shell. Renders every toast from useToasts(); Z runs the newest undo action. */
const { toasts, dismiss } = useToasts()

function run(id: number) {
  const t = toasts.value.find((x) => x.id === id)
  dismiss(id)
  t?.action?.run()
}
function onKey(e: KeyboardEvent) {
  if (e.key.toLowerCase() !== 'z' || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return
  const t = [...toasts.value].reverse().find((x) => x.action?.key?.toLowerCase() === 'z')
  if (!t) return
  e.preventDefault()
  run(t.id)
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="toast-stack" role="region" aria-label="Notifications" aria-live="polite">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="{ err: t.kind === 'err' }" :role="t.kind === 'err' ? 'alert' : 'status'">
      <Icon class="ico" :name="t.kind === 'err' ? 'warn' : 'check'" />
      <span>{{ t.message }}</span>
      <Btn v-if="t.action" size="sm" :kbd="t.action.key" @click="run(t.id)">{{ t.action.label }}</Btn>
      <Btn size="sm" variant="ghost" icon label="Dismiss" @click="dismiss(t.id)"><Icon name="x" :size="12" /></Btn>
    </div>
  </div>
</template>

<style scoped>
.toast-stack { position: fixed; right: var(--s-5); bottom: calc(var(--bar-h) + var(--s-4)); display: flex; flex-direction: column; gap: var(--s-2); z-index: var(--z-toast); align-items: flex-end; }
.toast { display: flex; align-items: center; gap: var(--s-3); padding: 10px 12px 10px 14px; border-radius: var(--r-lg); background: var(--n-3); border: 1px solid var(--line-strong); box-shadow: var(--e-2); color: var(--text); font-size: 13px; max-width: 460px; }
.ico { color: var(--good); flex: none; }
.err .ico { color: var(--bad); }
@media (max-width: 640px) { .toast-stack { right: var(--s-3); left: var(--s-3); } }
</style>
