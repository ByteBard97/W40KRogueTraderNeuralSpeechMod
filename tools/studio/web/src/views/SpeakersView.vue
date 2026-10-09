<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EmptyState from '../components/shared/EmptyState.vue'
import type { SpeakerStatus } from '../api/types'
import { useSpeakersStore } from '../stores/speakers'

const store = useSpeakersStore()
const filter = ref('')
onMounted(store.load)

const GROUPS: { status: SpeakerStatus; title: string }[] = [
  { status: 'needs_voice', title: 'Needs a voice' },
  { status: 'source', title: 'Has a source' },
  { status: 'profile', title: 'Profile saved' },
]

const visible = computed(() => {
  const q = filter.value.trim().toLowerCase()
  return GROUPS.map((g) => ({
    ...g,
    items: store.byStatus[g.status].filter((s) => !q || s.name.toLowerCase().includes(q)),
  })).filter((g) => g.items.length)
})
</script>

<template>
  <div>
    <input v-model="filter" placeholder="filter speakers" />
    <p v-if="store.error" class="err">{{ store.error }}</p>
    <EmptyState v-else-if="!store.list.length && !store.loading" message="No speakers yet." />
    <EmptyState v-else-if="!visible.length" message="No speakers match the filter." />
    <section v-for="g in visible" :key="g.status">
      <h2>{{ g.title }} <span class="dim">{{ g.items.length }}</span></h2>
      <RouterLink v-for="s in g.items" :key="s.slug" class="row" :to="`/speakers/${s.slug}`">
        <b>{{ s.name }}</b>
        <span class="chip">{{ s.origin }}</span>
        <span class="dim">{{ s.line_count }} lines</span>
      </RouterLink>
    </section>
  </div>
</template>

<style scoped>
h2 { font-size: 14px; margin: 16px 0 4px; }
.row { display: flex; gap: 10px; align-items: center; padding: 6px 8px; border-bottom: 1px solid var(--line); text-decoration: none; color: var(--fg); }
.row:hover { background: var(--card); }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); }
</style>
