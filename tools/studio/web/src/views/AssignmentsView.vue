<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AssignmentDetail from '../components/assignments/AssignmentDetail.vue'
import AssignmentList from '../components/assignments/AssignmentList.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import Btn from '../components/ui/Btn.vue'
import InlineError from '../components/ui/InlineError.vue'
import SearchField from '../components/ui/SearchField.vue'
import Seg from '../components/ui/Seg.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useAssignmentsStore, type AssignmentFilter, type AssignmentKind } from '../stores/assignments'

const store = useAssignmentsStore()
onMounted(() => store.load())

const STATUSES = [{ value: 'all' as AssignmentFilter, label: 'All' }, { value: 'assigned' as AssignmentFilter, label: 'Has a voice' }, { value: 'needs_info' as AssignmentFilter, label: 'Needs info' }, { value: 'mine' as AssignmentFilter, label: 'Mine' }]
const KINDS = [{ value: 'all' as AssignmentKind, label: 'Both' }, { value: 'character' as AssignmentKind, label: 'Characters' }, { value: 'group' as AssignmentKind, label: 'Groups' }]
const firstLoad = computed(() => store.loading && !store.page)
const counts = computed(() => store.summary)
</script>

<template>
  <div class="page assignments">
    <div class="page-head">
      <div class="titles">
        <h1 class="page-title">Assignments</h1>
        <span class="page-sub">The BG3 voice picked for every character without one, using your labels. Play each one, check the reasons, and change any you disagree with. Nothing here is rendered or registered until you say so.</span>
      </div>
      <div class="progress">
        <b>{{ counts.assigned ?? 0 }}</b> have a voice · <b>{{ counts.needs_info ?? 0 }}</b> need more information
        <Btn size="sm" :disabled="store.running" @click="store.rerun()">{{ store.running ? 'Working…' : 'Work them out again' }}</Btn>
      </div>
    </div>

    <InlineError v-if="store.error" title="Assignments problem"> {{ store.error }} <Btn size="sm" @click="store.load()">Retry</Btn></InlineError>

    <Skeleton v-if="firstLoad" :rows="6" />
    <div v-else-if="store.page" class="split">
      <div class="side">
        <div class="filters">
          <Seg v-model="store.kind" :options="KINDS" aria-label="Characters or groups" />
          <Seg v-model="store.status" :options="STATUSES" aria-label="Which to show" />
          <SearchField v-model="store.query" placeholder="Find a character or voice" label="Find a character or voice" />
        </div>
        <EmptyState v-if="!store.visible.length" message="Nothing matches these filters." />
        <AssignmentList v-else :rows="store.visible" :selected="store.current?.key ?? null" @select="store.select" />
      </div>
      <div v-if="store.current" class="main">
        <AssignmentDetail :item="store.current" :voice="store.voiceOf(store.current)" :voices="store.voices" @pick="store.override(store.current.key, $event)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.titles { display: flex; flex-direction: column; gap: var(--s-1); flex: 1 1 360px; min-width: 0; }
.progress { margin-left: auto; display: flex; align-items: center; gap: var(--s-3); flex-wrap: wrap; color: var(--text-2); }
.filters { display: flex; flex-direction: column; gap: var(--s-2); }
.side { max-width: 420px; }
@media (max-width: 480px) { .progress { margin-left: 0; } .side { max-width: none; flex-basis: 100%; } }
</style>
