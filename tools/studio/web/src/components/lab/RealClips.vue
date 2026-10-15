<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../../api/client'
import type { LabRealClip } from '../../api/labTypes'
import Btn from '../ui/Btn.vue'
import InlinePlay from '../ui/InlinePlay.vue'

/** The game's real voice clips whose text contains the query: hear how the actors say the word. */
const props = defineProps<{ word: string }>()
const CLIP_LIMIT = 12
const q = ref(props.word)
const clips = ref<LabRealClip[]>([])
const searched = ref(false)
const error = ref<string | null>(null)
const edited = ref(false)

watch(() => props.word, (w) => {
  if (!edited.value) q.value = w
})
async function search() {
  if (!q.value.trim()) return
  error.value = null
  try {
    clips.value = await api.labRealClips(q.value.trim(), CLIP_LIMIT)
    searched.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
</script>

<template>
  <div class="real" data-real-clips>
    <h3 class="sub">Real clips</h3>
    <form class="bar" @submit.prevent="search">
      <label class="field"><span class="lbl">Text contains</span><input v-model="q" data-real-q @input="edited = true" /></label>
      <Btn size="sm" type="submit" :disabled="!q.trim()">Find</Btn>
    </form>
    <p v-if="error" class="err" data-real-error>{{ error }}</p>
    <ul v-if="clips.length" class="list">
      <li v-for="c in clips" :key="c.wav" data-real-clip>
        <InlinePlay :id="c.wav" :title="c.speaker" :subtitle="c.text" />
        <span class="who">{{ c.speaker }}</span>
        <span class="num muted">{{ c.seconds.toFixed(1) }}s</span>
        <span class="txt">{{ c.text }}</span>
      </li>
    </ul>
    <p v-else-if="searched" class="muted">No real clip contains that.</p>
  </div>
</template>

<style scoped>
.real { margin-top: var(--s-3); display: flex; flex-direction: column; gap: var(--s-2); }
.sub { margin: 0; font-size: var(--fs-sm); color: var(--text-2); text-transform: uppercase; letter-spacing: 0.06em; }
.bar { display: flex; gap: var(--s-2); align-items: center; flex-wrap: wrap; }
.err { color: var(--bad); margin: 0; }
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--s-1); }
.list li { display: flex; gap: var(--s-2); align-items: center; font-size: 13px; }
.who { font-weight: 600; flex: none; }
.txt { color: var(--text-2); min-width: 0; }
</style>
