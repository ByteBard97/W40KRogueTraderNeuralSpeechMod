<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { spreadPick } from '../../utils/spread'
import EmptyState from '../shared/EmptyState.vue'

const LINE_RENDER_CAP = 200
const ctx = useSpeakerContext()
const { play } = useAudioPlayer()
const query = ref('')
const emotion = ref<string | null>(null)
const shown = ref(LINE_RENDER_CAP)

const emotions = computed(() => [...new Set(ctx.lines.value.map((l) => l.emotion).filter((e): e is string => !!e))].sort())
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return ctx.lines.value.filter((l) => (!emotion.value || l.emotion === emotion.value) && (!q || l.text.toLowerCase().includes(q)))
})
const visible = computed(() => filtered.value.slice(0, shown.value))

function toggle(guid: string, on: boolean) {
  const next = new Set(ctx.selectedLines.value)
  on ? next.add(guid) : next.delete(guid)
  ctx.selectedLines.value = next
}
const spread = () => (ctx.selectedLines.value = new Set(spreadPick(ctx.lines.value)))
const clear = () => (ctx.selectedLines.value = new Set())
</script>

<template>
  <EmptyState v-if="!ctx.lines.value.length" message="No lines for this speaker." />
  <div v-else>
    <div class="tools">
      <input type="search" v-model="query" placeholder="search text" />
      <button data-emo="" :class="{ on: !emotion }" @click="emotion = null">all</button>
      <button v-for="e in emotions" :key="e" :data-emo="e" :class="{ on: emotion === e }" @click="emotion = e">{{ e }}</button>
      <button data-spread @click="spread">Pick 6 spread across emotions</button>
      <button data-clear @click="clear">Clear</button>
      <span class="dim">{{ filtered.length }} lines, {{ ctx.selectedLines.value.size }} ticked</span>
    </div>
    <div v-for="l in visible" :key="l.guid" class="line">
      <input type="checkbox" :checked="ctx.selectedLines.value.has(l.guid)" @change="toggle(l.guid, ($event.target as HTMLInputElement).checked)" />
      <button class="play" :disabled="!l.baseline" :title="l.baseline ? 'the bank render of this line' : 'no bank render'" @click="l.baseline && play(l.baseline)">▶</button>
      <div>
        <span class="chip">{{ l.emotion ?? '—' }} {{ l.intensity ?? '' }}</span><span class="chip">{{ l.pace ?? '—' }}</span>
        <div>{{ l.text }}</div>
        <div v-if="l.instruct" class="dim">style: {{ l.instruct }}</div>
      </div>
    </div>
    <button v-if="filtered.length > shown" data-more @click="shown += LINE_RENDER_CAP">Show {{ LINE_RENDER_CAP }} more</button>
  </div>
</template>

<style scoped>
.tools { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; margin-bottom: 8px; }
.tools .on { background: var(--acc); color: #0b1220; border-color: var(--acc); }
.line { display: grid; grid-template-columns: 22px 30px 1fr; gap: 6px; padding: 6px 0; border-top: 1px solid var(--line); align-items: start; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); margin-right: 4px; }
.dim { color: var(--dim); font-size: 12px; }
</style>
