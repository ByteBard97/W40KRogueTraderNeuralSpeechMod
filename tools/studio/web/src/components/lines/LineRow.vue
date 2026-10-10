<script setup lang="ts">
import type { Line } from '../../api/types'
import InlinePlay from '../ui/InlinePlay.vue'
import Tag from '../ui/Tag.vue'

defineProps<{ line: Line; ticked: boolean; speaker: string }>()
const emit = defineEmits<{ toggle: [on: boolean] }>()
</script>

<template>
  <div class="tl" :class="{ on: ticked }">
    <input type="checkbox" aria-label="Use this line" :checked="ticked" @change="emit('toggle', ($event.target as HTMLInputElement).checked)" />
    <InlinePlay :id="line.baseline" :title="`${speaker} · bank render`" :subtitle="line.baseline ?? ''" unavailable-reason="No bank render of this line" />
    <div class="body">
      <div class="meta">
        <Tag>{{ line.emotion ?? '—' }}{{ line.intensity !== null && line.intensity !== undefined ? ` ${line.intensity}` : '' }}</Tag>
        <Tag>{{ line.pace ?? '—' }}</Tag>
        <span v-if="line.dur" class="num muted dur">{{ line.dur.toFixed(1) }} s</span>
      </div>
      <div class="txt">{{ line.text }}</div>
      <div v-if="line.instruct" class="sty muted">style: {{ line.instruct }}</div>
    </div>
  </div>
</template>

<style scoped>
.tl { display: grid; grid-template-columns: 20px 32px minmax(0, 1fr); gap: 4px 10px; align-items: start; padding: 8px 6px; border-top: 1px solid var(--line); }
input { accent-color: var(--accent); width: 16px; height: 16px; margin-top: 8px; }
.meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 2px; }
.dur { font-size: var(--fs-xs); }
.txt { font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; }
.sty { font-size: var(--fs-sm); }
</style>
