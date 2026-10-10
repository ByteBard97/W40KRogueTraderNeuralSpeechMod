<script setup lang="ts">
import { ref } from 'vue'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import Btn from '../ui/Btn.vue'
import DataRow from '../ui/DataRow.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import Tag from '../ui/Tag.vue'

const ctx = useSpeakerContext()
const wav = ref('')
const text = ref('')
function add() {
  if (!wav.value.trim()) return
  ctx.addSupplied(wav.value.trim(), text.value.trim())
  wav.value = text.value = ''
}
function toggle(key: string, on: boolean) {
  const next = new Set(ctx.selectedSources.value)
  if (on) next.add(key)
  else next.delete(key)
  ctx.selectedSources.value = next
}
</script>

<template>
  <div class="supplied">
    <p class="muted hint">Any wav under <span class="mono">data/</span> can be a source: give its repo path and what is said in it.</p>
    <form class="add" @submit.prevent="add">
      <label class="field grow"><span class="lbl">Wav path</span><input v-model="wav" data-wav placeholder="data/… .wav" /></label>
      <label class="field grow"><span class="lbl">Transcript</span><input v-model="text" placeholder="what the clip says" /></label>
      <Btn type="submit" :disabled="!wav.trim()">Add as source</Btn>
    </form>
    <div v-if="ctx.supplied.value.length" class="list">
      <DataRow v-for="s in ctx.supplied.value" :key="s.key" :selected="ctx.selectedSources.value.has(s.key)">
        <template #lead>
          <input type="checkbox" :aria-label="`Clone from ${s.label}`" :checked="ctx.selectedSources.value.has(s.key)" @change="toggle(s.key, ($event.target as HTMLInputElement).checked)" />
          <InlinePlay :id="s.wav" :title="s.label" :subtitle="s.wav" />
        </template>
        <span class="text">{{ s.text || 'no transcript' }}</span>
        <template #meta><Tag variant="plain">{{ s.label }}</Tag></template>
      </DataRow>
    </div>
  </div>
</template>

<style scoped>
.supplied { display: flex; flex-direction: column; gap: var(--s-3); }
.hint { margin: 0; font-size: var(--fs-sm); }
.add { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.grow { flex: 1 1 220px; }
.list { border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--surface); }
input[type='checkbox'] { accent-color: var(--accent); width: 16px; height: 16px; }
.text { font-size: 13px; color: var(--text-2); overflow-wrap: anywhere; }
</style>
