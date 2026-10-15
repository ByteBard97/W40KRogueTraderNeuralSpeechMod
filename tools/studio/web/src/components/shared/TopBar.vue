<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useNavCountsStore } from '../../stores/navCounts'
import { useShortcutOverlay } from '../../composables/useShortcuts'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import Kbd from '../ui/Kbd.vue'
import ModelPill from '../ui/ModelPill.vue'

const counts = useNavCountsStore()
const overlay = useShortcutOverlay()
onMounted(() => counts.load())
const fmt = (n: number) => n.toLocaleString('en-US')

const links = computed(() => [
  { to: '/speakers', label: 'Speakers', count: counts.speakersLeft === null ? null : `${fmt(counts.speakersLeft)} left` },
  { to: '/pools', label: 'Pools', count: counts.pools === null ? null : fmt(counts.pools) },
  { to: '/fx', label: 'FX', count: counts.fxUnsaved ? `${counts.fxUnsaved} unsaved` : null },
  { to: '/matches', label: 'Matches', count: counts.matchesUndecided === null ? null : fmt(counts.matchesUndecided) },
  { to: '/casting', label: 'Casting', count: null },
  { to: '/voices', label: 'BG3 Voices', count: null },
  { to: '/lab', label: 'Render Lab', count: null },
  { to: '/qa', label: 'Render QA', count: counts.qaClips === null ? null : fmt(counts.qaClips) },
])
</script>

<template>
  <header class="topbar">
    <div class="brand"><Icon name="brand" :size="18" />Voice Studio</div>
    <nav class="nav" aria-label="Sections">
      <RouterLink v-for="l in links" :key="l.to" :to="l.to">{{ l.label }}<span v-if="l.count" class="count">{{ l.count }}</span></RouterLink>
    </nav>
    <div class="right">
      <ModelPill />
      <Btn variant="ghost" icon label="Keyboard shortcuts" @click="overlay.toggle()"><Kbd>?</Kbd></Btn>
    </div>
  </header>
</template>

<style scoped>
.topbar { position: sticky; top: 0; z-index: var(--z-topbar); min-height: var(--topbar-h); display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-5); padding: var(--s-2) var(--s-5); background: var(--n-1); border-bottom: 1px solid var(--line); }
.brand { font-family: var(--font-display); font-weight: 600; letter-spacing: 0.06em; font-size: 15px; color: var(--text); white-space: nowrap; display: flex; align-items: center; gap: var(--s-2); }
.brand svg { color: var(--accent); }
.nav { display: flex; flex-wrap: wrap; gap: 2px; flex: 1 1 auto; }
.nav a { display: inline-flex; align-items: center; gap: 6px; min-height: 32px; padding: 0 var(--s-3); border-radius: var(--r-md); color: var(--text-2); text-decoration: none; font-weight: 500; }
.nav a:hover { background: var(--hover); color: var(--text); }
.nav a[aria-current="page"] { color: var(--text); background: var(--inset); box-shadow: inset 0 -2px 0 var(--accent); }
.count { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); }
.right { display: flex; align-items: center; gap: var(--s-2); margin-left: auto; }
@media (max-width: 640px) {
  .topbar { padding: var(--s-2) var(--s-3); gap: var(--s-2); }
  .nav { order: 3; flex: 1 1 100%; overflow-x: auto; flex-wrap: nowrap; }
}
</style>
