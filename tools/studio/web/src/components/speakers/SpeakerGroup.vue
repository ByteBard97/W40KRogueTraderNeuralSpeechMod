<script setup lang="ts">
import type { SpeakerRow as Row } from '../../utils/speakerRows'
import SpeakerRow from './SpeakerRow.vue'

/** One card of the list: a heading with a count, rows, and optionally a second block of slot voices under a sub-head. */
defineProps<{
  title: string
  /** Count in the heading: the unfiltered size of the group. */
  total: number
  rows: Row[]
  slotRows?: Row[]
  slotNote?: string
  current: string | null
  emptyTitle?: string
  emptyMessage?: string
}>()
</script>

<template>
  <section class="vs-card grp" :aria-label="title">
    <div class="list-head">{{ title }} <span class="n">{{ total }}</span></div>
    <SpeakerRow v-for="r in rows" :key="r.speaker.slug" :row="r" :current="current === r.speaker.slug" />
    <template v-if="slotRows?.length">
      <div class="sub-head">{{ slotNote }}</div>
      <SpeakerRow v-for="r in slotRows" :key="r.speaker.slug" :row="r" :current="current === r.speaker.slug" />
    </template>
    <div v-if="!total && emptyTitle" class="empty-note">
      <span class="t">{{ emptyTitle }}</span>
      <span>{{ emptyMessage }}</span>
    </div>
  </section>
</template>

<style scoped>
.grp { padding: var(--s-1); }
.sub-head { padding: 10px var(--s-3) var(--s-1); font-size: var(--fs-sm); color: var(--text-3); border-top: 1px solid var(--line); }
.empty-note { display: flex; flex-direction: column; align-items: center; gap: var(--s-2); margin: var(--s-1) var(--s-2) var(--s-3); padding: var(--s-5) var(--s-4); text-align: center; color: var(--text-3); font-size: 13px; border: 1px dashed var(--line-strong); border-radius: var(--r-lg); }
.t { color: var(--text); font-weight: 600; font-size: 15px; }
</style>
