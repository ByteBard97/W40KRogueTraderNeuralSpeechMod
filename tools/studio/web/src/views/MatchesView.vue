<script setup lang="ts">
import { onMounted } from 'vue'
import MatchFilters from '../components/matches/MatchFilters.vue'
import MatchRow from '../components/matches/MatchRow.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import { useMatchesStore } from '../stores/matches'

const matches = useMatchesStore()
onMounted(() => matches.load())
</script>

<template>
  <div>
    <h1>Matches</h1>
    <p class="dim">
      Each row is a character the harness found in an unattributed conversation, matched to a speaker the game already names.
      Accept it to use that speaker's voice; reject it and the character gets a shared or designed voice instead.
      Decisions save as you click and keep the Pools routing in step.
    </p>
    <p v-if="matches.page" class="dim">
      {{ matches.page.total }} shown · flagged {{ matches.page.counts.flagged }} · with bank {{ matches.page.counts.bank }} ·
      without bank {{ matches.page.counts.nobank }} · undecided {{ matches.page.counts.undecided }}
    </p>
    <p v-if="matches.error" class="err">{{ matches.error }}</p>
    <p v-if="matches.notice" class="ok">{{ matches.notice }}</p>
    <MatchFilters @change="matches.setFilter" />
    <EmptyState v-if="!matches.items.length && !matches.loading" message="No matches for these filters." />
    <MatchRow v-for="r in matches.items" :key="r.id" :row="r" @decide="matches.decide(r.id, $event)" />
    <button v-if="matches.remaining > 0" data-more @click="matches.load(true)">
      Show more ({{ matches.remaining }} left)
    </button>
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); }
.ok { color: var(--ok); }
</style>
