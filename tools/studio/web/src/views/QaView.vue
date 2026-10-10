<script setup lang="ts">
import { markRaw, onBeforeUnmount, onMounted, ref } from 'vue'
import QaClipCard from '../components/qa/QaClipCard.vue'
import QaFilters from '../components/qa/QaFilters.vue'
import QaProgress from '../components/qa/QaProgress.vue'
import QaQueue from '../components/qa/QaQueue.vue'
import { useQaReview } from '../components/qa/useQaReview'
import EmptyState from '../components/shared/EmptyState.vue'
import InlineError from '../components/ui/InlineError.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useGlobalAudio } from '../composables/globalAudio'
import { useQaKeys } from '../composables/useQaKeys'
import { useShortcuts } from '../composables/useShortcuts'

const { qa, fx, init, pickRun, applyFilter, judge, setTags, setNote, nextUnjudged, handler } = useQaReview()
const audio = useGlobalAudio()
const card = ref<InstanceType<typeof QaClipCard> | null>(null)

useShortcuts({
  title: 'Render QA',
  groups: [
    { title: 'Move', items: [{ label: 'Next / previous clip', keys: ['J', 'K'] }, { label: 'Next unjudged', keys: ['N'] }] },
    { title: 'Judge', items: [
      { label: 'Good / bad', keys: ['G', 'B'] }, { label: 'Clear verdict', keys: ['U'] }, { label: 'Undo last verdict', keys: ['Z'] },
      { label: 'Toggle tag (also marks the clip bad)', keys: ['1', '–', '9', '0'] },
    ] },
    { title: 'Listen', items: [
      { label: 'Play / pause the chosen source', keys: ['Space'] }, { label: 'Clip, reference, earlier render, real line', keys: ['A', 'S', 'D', 'F'] },
      { label: 'Compressor on / off', keys: ['X'] }, { label: 'Search line text', keys: ['/'] },
    ] },
  ],
})
useQaKeys(handler(() => card.value?.playSelected()))

// markRaw: the player keeps it in reactive state, and clearTransport compares by identity
const transport = markRaw({ prev: () => qa.move(-1), next: () => qa.move(1) })
onMounted(() => {
  audio.setTransport(transport)
  void init()
})
onBeforeUnmount(() => audio.clearTransport(transport))
</script>

<template>
  <div class="page qa">
    <h1 class="vh">Render QA</h1>
    <QaFilters
      v-model:fx="fx"
      :runs="qa.runs"
      :run="qa.run"
      :facets="qa.facets"
      :filter="qa.filter"
      :matching="qa.total"
      :in-run="qa.runs.find((r) => r.id === qa.run)?.clips ?? qa.total"
      @update:run="pickRun"
      @change="applyFilter"
    />
    <QaProgress :stats="qa.stats" :view="qa.view" :session="qa.session" />
    <InlineError v-if="qa.error" title="Something went wrong"><div data-error>{{ qa.error }}</div></InlineError>

    <div class="split">
      <section class="main" aria-label="Current clip">
        <QaClipCard
          v-if="qa.current"
          ref="card"
          :clip="qa.current"
          :position="qa.offset + qa.index + 1"
          :total="qa.total"
          :fx="fx"
          @verdict="judge"
          @tags="setTags(qa.current.guid, $event)"
          @note="setNote(qa.current.guid, $event)"
          @next-unjudged="nextUnjudged"
        />
        <Skeleton v-else-if="qa.loading" :rows="6" />
        <EmptyState v-else message="No clips for these filters." />
      </section>
      <aside class="side sticky queue-side" aria-label="Queue">
        <QaQueue
          :items="qa.items"
          :index="qa.index"
          :total="qa.total"
          :has-next="qa.hasNext"
          :loading="qa.loading"
          :sort-label="qa.filter.sort ?? 'suspicious'"
          @select="qa.select"
          @more="qa.loadMore"
        />
      </aside>
    </div>
  </div>
</template>

<style scoped>
.qa { display: flex; flex-direction: column; gap: var(--s-3); }
.queue-side { flex: 1 1 340px; max-width: 420px; }
@media (max-width: 960px) { .queue-side { position: static; max-width: none; } }
</style>
