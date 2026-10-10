<script setup lang="ts">
import type { MatchRowData } from '../../api/types'
import Btn from '../ui/Btn.vue'
import MatchRow from './MatchRow.vue'

/** The list on the left: every loaded match, the current one highlighted, and a button for the next page. */
defineProps<{ title: string; total: number; rows: MatchRowData[]; selectedId: string | null; remaining: number; busy: boolean }>()
defineEmits<{ select: [id: string]; more: [] }>()
</script>

<template>
  <aside class="queue" aria-label="Queue">
    <div class="list-head">{{ title }} <span class="n">{{ total }}</span></div>
    <MatchRow v-for="r in rows" :key="r.id" :row="r" :selected="r.id === selectedId" @select="$emit('select', r.id)" />
    <div v-if="remaining > 0" class="more"><Btn size="sm" :disabled="busy" data-more @click="$emit('more')">Show more ({{ remaining }} left)</Btn></div>
    <div class="row-hint muted">J K move · A accept · R reject · N next unreviewed · Z undo</div>
  </aside>
</template>

<style scoped>
.queue { padding: var(--s-1); border-radius: var(--r-lg); background: var(--surface); border: 1px solid var(--line); min-width: 0; }
.more { padding: var(--s-2) var(--s-3); }
.row-hint { font-size: var(--fs-sm); padding: var(--s-3); border-top: 1px solid var(--line); }
</style>
