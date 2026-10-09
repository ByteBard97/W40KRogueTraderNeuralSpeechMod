<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import EmptyState from '../shared/EmptyState.vue'

const FX_LAB_URL = 'http://127.0.0.1:8908'
const ctx = useSpeakerContext()

function toggle(name: string) {
  const cur = ctx.fxChosen.value
  ctx.fxChosen.value = cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]
}
</script>

<template>
  <EmptyState v-if="!ctx.fxAvailable.value.length" message="No FX presets found." />
  <div v-else>
    <p class="dim">
      Presets run in the order you pick them, on the raw clone. The real clips are often already processed, so a clone from one may be processed twice.
      Tune the presets themselves in the <a :href="FX_LAB_URL" target="_blank" rel="noopener">FX Lab</a>.
    </p>
    <div class="presets">
      <button v-for="n in ctx.fxAvailable.value" :key="n" :data-fx="n" :class="{ on: ctx.fxChosen.value.includes(n) }" @click="toggle(n)">
        {{ ctx.fxChosen.value.includes(n) ? `${ctx.fxChosen.value.indexOf(n) + 1}. ` : '' }}{{ n }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.presets { display: flex; gap: 6px; flex-wrap: wrap; }
.on { background: var(--acc); color: var(--on-acc); border-color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
</style>
