<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../../api/client'
import type { SpotSample } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

const props = defineProps<{ slotId: string }>()
const sample = ref<SpotSample | null>(null)
const verdicts = reactive<Record<string, boolean>>({})
const result = ref('')
const error = ref('')

const complete = computed(() => !!sample.value?.items.length && sample.value.items.every((i) => i.guid in verdicts))

async function load() {
  error.value = ''
  try {
    sample.value = await api.poolSpot(props.slotId)
    for (const k of Object.keys(verdicts)) delete verdicts[k]
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
async function submit() {
  try {
    const r = await api.poolSpotRecord(props.slotId, { ...verdicts })
    result.value = `${r.checked} checked, ${r.wrong} wrong`
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
onMounted(load)
</script>

<template>
  <div>
    <p v-if="error" class="err">{{ error }}</p>
    <EmptyState v-if="sample && !sample.items.length" message="Nothing left to check in this slot." />
    <div v-for="i in sample?.items ?? []" :key="i.guid" class="line">
      <span class="text">{{ i.text }}</span>
      <button data-ok :class="{ on: verdicts[i.guid] === true }" @click="verdicts[i.guid] = true">✓</button>
      <button data-wrong :class="{ on: verdicts[i.guid] === false }" @click="verdicts[i.guid] = false">✗</button>
    </div>
    <button v-if="sample?.items.length" data-submit :disabled="!complete" @click="submit">Submit {{ sample.items.length }} checks</button>
    <span class="dim">{{ result }}</span>
  </div>
</template>

<style scoped>
.line { display: flex; gap: 8px; align-items: center; padding: 3px 0; }
.text { flex: 1; }
button.on { background: var(--acc); color: #0b1220; border-color: var(--acc); }
.err { color: var(--bad); }
.dim { color: var(--dim); font-size: 12px; margin-left: 8px; }
</style>
