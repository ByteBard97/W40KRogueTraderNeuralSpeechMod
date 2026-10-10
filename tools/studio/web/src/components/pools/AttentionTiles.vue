<script setup lang="ts">
import Btn from '../ui/Btn.vue'

/** The three numbers that say what is left to do on this page. */
defineProps<{ queueEntries: number; queueLines: number; threshold: number; checked: number; slotTotal: number; overrides: number; hasNextSlot: boolean }>()
const emit = defineEmits<{ review: []; nextSlot: [] }>()
const fmt = (n: number) => n.toLocaleString('en-US')
</script>

<template>
  <div class="tiles" aria-label="Needs your attention">
    <div class="tile" :class="{ hot: queueEntries > 0 }" data-tile-review>
      <span class="big">{{ fmt(queueEntries) }}</span>
      <span class="cap">{{ queueEntries === 1 ? 'roster entry' : 'roster entries' }} to review · {{ fmt(queueLines) }} lines below {{ threshold }} confidence</span>
      <Btn v-if="queueEntries > 0" size="sm" variant="primary" kbd="R" class="act" @click="emit('review')">Start review</Btn>
    </div>
    <div class="tile" :class="{ hot: hasNextSlot }" data-tile-slots>
      <span class="big">{{ checked }} / {{ slotTotal }}</span>
      <span class="cap">slots spot-checked · a sample of lines each</span>
      <Btn v-if="hasNextSlot" size="sm" class="act" @click="emit('nextSlot')">Next unchecked slot</Btn>
    </div>
    <div class="tile" data-tile-overrides>
      <span class="big">{{ fmt(overrides) }}</span>
      <span class="cap">per-line overrides · set from the routes table</span>
    </div>
  </div>
</template>

<style scoped>
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: var(--s-3); }
.tile { display: flex; flex-direction: column; gap: 6px; padding: 14px var(--s-4); border-radius: var(--r-lg); background: var(--surface); border: 1px solid var(--line); }
.tile.hot { border-color: var(--warn-line); background: linear-gradient(0deg, var(--warn-tint), var(--warn-tint)), var(--surface); }
.big { font: 600 26px/1 var(--font-mono); color: var(--text); }
.cap { font-size: 13px; color: var(--text-2); }
.act { align-self: flex-start; }
</style>
