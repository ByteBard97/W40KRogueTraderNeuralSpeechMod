<script setup lang="ts">
import { computed } from 'vue'
import EmptyState from '../components/shared/EmptyState.vue'
import RegisterAllPanel from '../components/speakers/RegisterAllPanel.vue'
import SpeakerGroup from '../components/speakers/SpeakerGroup.vue'
import SpeakerHero from '../components/speakers/SpeakerHero.vue'
import Btn from '../components/ui/Btn.vue'
import FilterBar from '../components/ui/FilterBar.vue'
import InlineError from '../components/ui/InlineError.vue'
import SearchField from '../components/ui/SearchField.vue'
import Seg from '../components/ui/Seg.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useRegisterAll } from '../composables/useRegisterAll'
import { useShortcuts } from '../composables/useShortcuts'
import { useSpeakerList } from '../composables/useSpeakerList'

const reg = useRegisterAll()
const locked = computed(() => reg.phase.value === 'confirm')
const list = useSpeakerList(locked)
const { store, counts } = list

const showOptions = computed(() => [
  { value: 'all' as const, label: `All ${counts.value.total}` },
  { value: 'todo' as const, label: `Unfinished ${counts.value.total - counts.value.done}` },
  { value: 'done' as const, label: `Done ${counts.value.done}` },
])
const slotNote = computed(() => {
  const n = list.slotLineTotal.value
  return n ? `Shared slot voices · used by ${n.toLocaleString('en-US')} unnamed lines via Pools` : 'Shared slot voices · used by unnamed lines via Pools'
})

useShortcuts({
  title: 'Speakers',
  groups: [{
    title: 'List',
    items: [
      { label: 'Filter', keys: ['/'] },
      { label: 'Move down / up', keys: ['J', 'K'] },
      { label: 'Open the highlighted speaker', keys: ['Enter'] },
      { label: 'Play the highlighted speaker', keys: ['Space'] },
      { label: 'Continue with the next unfinished speaker', keys: ['N'] },
    ],
  }],
})
</script>

<template>
  <div class="page">
    <SpeakerHero :counts="counts" :next="list.next.value" :picks="reg.picks.value" :busy="reg.phase.value === 'busy'" @continue="list.goNext" @register="reg.ask" />
    <RegisterAllPanel :phase="reg.phase.value" :picks="reg.picks.value" :skipped="reg.skipped.value" :result="reg.result.value" :error="reg.error.value" @confirm="reg.run" @dismiss="reg.dismiss" />

    <FilterBar>
      <SearchField v-model="list.q.value" class="grow" placeholder="Filter speakers" label="Filter speakers" />
      <Seg v-model="list.show.value" :options="showOptions" aria-label="Show" />
      <span class="hint hide-sm">J K move · Enter open · N next unfinished</span>
    </FilterBar>

    <InlineError v-if="store.error" title="Could not load speakers">
      <span> {{ store.error }} </span>
      <Btn size="sm" @click="store.load()">Retry</Btn>
    </InlineError>
    <Skeleton v-else-if="store.loading && !store.list.length" :rows="8" />
    <EmptyState v-else-if="!store.list.length" title="No speakers yet" message="Speakers appear once the design manifest or the prompt bank has entries." />
    <EmptyState v-else-if="!list.shown.value.length" title="No speakers match" message="Clear the filter or switch the view to All." />
    <div v-else class="cols">
      <SpeakerGroup
        v-if="list.groups.value.named.length || list.groups.value.slots.length"
        title="Needs a voice"
        :total="list.totals.value.needs"
        :rows="list.groups.value.named"
        :slot-rows="list.groups.value.slots"
        :slot-note="slotNote"
        :current="list.cursor.value"
      />
      <div class="stack">
        <SpeakerGroup v-if="list.groups.value.source.length" title="Has a source" :total="list.totals.value.source" :rows="list.groups.value.source" :current="list.cursor.value" />
        <SpeakerGroup
          v-if="list.groups.value.profile.length || (!list.totals.value.profile && !list.q.value && list.show.value === 'all')"
          title="Profile saved"
          :total="list.totals.value.profile"
          :rows="list.groups.value.profile"
          :current="list.cursor.value"
          empty-title="No saved profiles yet"
          empty-message="Speakers move here when you press Save profile on their workbench."
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(460px, 100%), 1fr)); gap: var(--s-4); align-items: start; }
.stack { display: flex; flex-direction: column; gap: var(--s-4); min-width: 0; }
.hint { margin-left: auto; font-size: var(--fs-sm); color: var(--text-3); padding-right: var(--s-2); }
</style>
