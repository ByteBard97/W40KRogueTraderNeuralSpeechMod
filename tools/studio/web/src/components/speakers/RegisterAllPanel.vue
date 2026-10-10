<script setup lang="ts">
import { computed } from 'vue'
import type { RegisterAllResult } from '../../api/types'
import type { RegisterPhase } from '../../composables/useRegisterAll'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import InlineConfirm from '../ui/InlineConfirm.vue'
import InlineError from '../ui/InlineError.vue'

const props = defineProps<{ phase: RegisterPhase; picks: number; skipped: number; result: RegisterAllResult | null; error: string }>()
const emit = defineEmits<{ confirm: []; dismiss: [] }>()

const REASON_TEXT: Record<string, string> = { no_pick: 'designed, no pick yet', real: 'real voice, nothing to register' }
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`

const groups = computed(() => {
  const by = new Map<string, string[]>()
  for (const s of props.result?.skipped ?? []) {
    const key = s.reason === 'error' ? 'error' : s.reason
    by.set(key, [...(by.get(key) ?? []), s.name])
  }
  return [...by].map(([reason, names]) => ({ reason, label: REASON_TEXT[reason] ?? reason, names }))
})
const failures = computed(() => (props.result?.skipped ?? []).filter((s) => s.reason === 'error'))
const okGroups = computed(() => groups.value.filter((g) => g.reason !== 'error'))
</script>

<template>
  <InlineConfirm v-if="phase === 'confirm'" confirm-label="Register" @confirm="emit('confirm')" @cancel="emit('dismiss')">
    Register <b>{{ plural(picks, 'pick') }}</b> as active voices (writes the prompt bank)? Speakers without a pick are skipped ({{ skipped }}).
  </InlineConfirm>
  <p v-else-if="phase === 'busy'" class="busy" role="status"><span class="spinner" /> Registering {{ plural(picks, 'pick') }}...</p>
  <InlineError v-else-if="phase === 'done' && error" title="Register all failed">
    <span class="detail"> {{ error }}</span>
    <Btn size="sm" variant="ghost" @click="emit('dismiss')">Dismiss</Btn>
  </InlineError>
  <div v-else-if="phase === 'done' && result" class="vs-card res" data-register-result>
    <div class="line">
      <span class="saved"><Icon name="check" :size="14" />Registered {{ result.registered.length }}</span>
      <span v-for="r in result.registered" :key="r.name" class="muted">· {{ r.name }}<template v-if="r.cand"> → {{ r.cand.replace(/\.[a-z0-9]+$/i, '') }}</template></span>
      <span class="muted">· skipped {{ result.skipped.length }}</span>
      <Btn class="dismiss" size="sm" variant="ghost" @click="emit('dismiss')">Dismiss</Btn>
    </div>
    <InlineError v-if="failures.length" title="Could not register">
      <ul class="fails"><li v-for="f in failures" :key="f.name">{{ f.name }}: {{ f.detail ?? 'error' }}</li></ul>
    </InlineError>
    <details v-if="okGroups.length">
      <summary class="muted">Skipped: {{ okGroups.map((g) => `${g.label} (${g.names.length})`).join(' · ') }}</summary>
      <div v-for="g in okGroups" :key="g.reason" class="names mono muted">{{ g.names.join(' · ') }}</div>
    </details>
  </div>
</template>

<style scoped>
.busy { display: flex; align-items: center; gap: var(--s-2); margin: 0; color: var(--text-2); font-size: 13px; }
.res { padding: 14px var(--s-4); display: flex; flex-direction: column; gap: var(--s-2); }
.line { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); }
.dismiss { margin-left: auto; }
summary { cursor: pointer; font-size: 13px; }
.names { padding-top: 6px; line-height: 1.7; }
.fails { margin: 4px 0 0; padding-left: var(--s-4); }
.detail { margin-right: var(--s-2); }
</style>
