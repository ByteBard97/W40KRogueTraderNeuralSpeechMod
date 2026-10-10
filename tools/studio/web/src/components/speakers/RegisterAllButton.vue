<script setup lang="ts">
import { ref } from 'vue'
import type { RegisterAllResult } from '../../api/types'
import { useSpeakersStore } from '../../stores/speakers'

const store = useSpeakersStore()
const busy = ref(false)
const result = ref<RegisterAllResult | null>(null)
const error = ref('')

async function registerAll() {
  const n = store.pickedCount
  if (!window.confirm(`Register ${n} picked voice${n === 1 ? '' : 's'} into the prompt bank? This writes data/voices/prompts.`)) return
  busy.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await store.registerAll()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <span class="wrap">
    <button data-register-all :disabled="busy" @click="registerAll">{{ busy ? 'registering…' : 'Register all picks' }}</button>
    <span v-if="error" class="err">{{ error }}</span>
    <span v-if="result" class="dim">
      Registered {{ result.registered.length }}<template v-if="result.registered.length"> ({{ result.registered.map((r) => r.name).join(', ') }})</template>.
      <template v-if="result.skipped.length">Skipped: <span v-for="s in result.skipped" :key="s.name" class="skip">{{ s.name }}: {{ s.detail ?? s.reason }}</span></template>
    </span>
  </span>
</template>

<style scoped>
.wrap { display: inline-flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.dim { color: var(--dim); font-size: 12px; }
.skip { display: block; color: var(--warn); }
.err { color: var(--bad); font-size: 13px; }
</style>
