<script setup lang="ts">
import { computed, onMounted } from 'vue'
import MatchDetail from '../components/matches/MatchDetail.vue'
import MatchFilters from '../components/matches/MatchFilters.vue'
import MatchProgress from '../components/matches/MatchProgress.vue'
import MatchQueue from '../components/matches/MatchQueue.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import Btn from '../components/ui/Btn.vue'
import InlineError from '../components/ui/InlineError.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useMatchReview } from '../composables/useMatchReview'
import { DEFAULT_FILTER, useMatchesStore } from '../stores/matches'
import { blurClickedButton } from '../utils/keys'

const matches = useMatchesStore()
const review = useMatchReview()
onMounted(() => matches.load())

const GROUP_NAMES: Record<string, string> = { flagged: 'Flagged', bank: 'Has bank', nobank: 'No bank', '': 'All matches' }
const STATE_NAMES: Record<string, string> = { unreviewed: 'not reviewed', reviewed: 'reviewed', accept: 'accepted', reject: 'rejected' }
const NOUNS: Record<string, string> = { flagged: 'flagged', bank: 'with a bank', nobank: 'without a bank', '': 'matches' }

const group = computed(() => matches.filter.group ?? '')
const total = computed(() => matches.page?.total ?? 0)
const queueTitle = computed(() => {
  const state = STATE_NAMES[matches.filter.state ?? '']
  return state ? `${GROUP_NAMES[group.value]}, ${state}` : GROUP_NAMES[group.value]
})
/** Decided rows leave the server's total, so count the position against what the queue holds plus what is still to load. */
const position = computed(() => `${matches.index + 1} of ${matches.items.length + matches.remaining} ${NOUNS[group.value]}`)
const filtered = computed(() => !!(matches.filter.speaker || matches.filter.q || matches.filter.group !== '' || matches.filter.state !== ''))
const firstLoad = computed(() => matches.loading && !matches.page)
const showAll = () => matches.setFilter({ group: '', state: '', speaker: '', q: '' })
const emptyMessage = computed(() => (matches.filter.state === 'unreviewed' ? 'Nothing left to review in this view.' : 'No matches for these filters.'))
const isDefault = computed(() => JSON.stringify({ ...DEFAULT_FILTER, ...matches.filter }) === JSON.stringify(DEFAULT_FILTER))
</script>

<template>
  <div class="page matches" @click="blurClickedButton">
    <div class="page-head">
      <div class="titles">
        <h1 class="page-title">Matches</h1>
        <span class="page-sub">Characters found in unattributed conversations, matched to a speaker the game names. Accept to use that speaker's voice; reject and the character gets a slot or designed voice.</span>
      </div>
      <div class="side-progress">
        <MatchProgress :counts="matches.counts" :saved="matches.saved && !matches.error" :note="matches.notice" />
      </div>
    </div>

    <InlineError v-if="matches.error" title="Could not load or save matches"> {{ matches.error }}
      <Btn size="sm" @click="matches.load()">Retry</Btn>
    </InlineError>

    <MatchFilters :model-value="matches.filter" :counts="matches.counts" @update:model-value="matches.setFilter" />

    <Skeleton v-if="firstLoad" :rows="6" />
    <EmptyState v-else-if="!matches.items.length && !matches.loading && !matches.error" :message="emptyMessage">
      <Btn v-if="!isDefault || filtered" size="sm" @click="showAll">Show all matches</Btn>
    </EmptyState>
    <div v-else-if="matches.items.length" class="split">
      <div class="side queue-col">
        <MatchQueue
          :title="queueTitle" :total="total" :rows="matches.items" :selected-id="matches.selectedId"
          :remaining="matches.remaining" :busy="matches.busy" @select="matches.select" @more="matches.load(true)"
        />
      </div>
      <div class="main">
        <MatchDetail
          v-if="matches.current" :row="matches.current" :position="position" :hearing="review.hearing.value"
          @decide="review.decide" @hear="review.hear" @prev="review.prev" @next="matches.nextUnreviewed"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.titles { display: flex; flex-direction: column; gap: var(--s-1); flex: 1 1 360px; min-width: 0; }
.side-progress { flex: 0 1 340px; margin-left: auto; display: flex; flex-direction: column; gap: var(--s-1); min-width: 0; }
.queue-col { max-width: 400px; }
@media (max-width: 480px) { .side-progress { margin-left: 0; flex-basis: 100%; } .queue-col { max-width: none; flex-basis: 100%; } }
</style>
