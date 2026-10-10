<script setup lang="ts">
import { computed, ref } from 'vue'
import ABCompareStrip from '../components/ui/ABCompareStrip.vue'
import ActiveFilters from '../components/ui/ActiveFilters.vue'
import AudioBar from '../components/ui/AudioBar.vue'
import BusyJobCard from '../components/ui/BusyJobCard.vue'
import Btn from '../components/ui/Btn.vue'
import DataRow from '../components/ui/DataRow.vue'
import FilterBar from '../components/ui/FilterBar.vue'
import FilterChips from '../components/ui/FilterChips.vue'
import Flag from '../components/ui/Flag.vue'
import InlineConfirm from '../components/ui/InlineConfirm.vue'
import InlineError from '../components/ui/InlineError.vue'
import InlinePlay from '../components/ui/InlinePlay.vue'
import JudgePair, { type Verdict } from '../components/ui/JudgePair.vue'
import SavedIndicator from '../components/ui/SavedIndicator.vue'
import ScoreChip from '../components/ui/ScoreChip.vue'
import SearchField from '../components/ui/SearchField.vue'
import SelectField from '../components/ui/SelectField.vue'
import Seg from '../components/ui/Seg.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import StatusDot, { type DotStatus } from '../components/ui/StatusDot.vue'
import Tag from '../components/ui/Tag.vue'
import Toast from '../components/ui/Toast.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import SectionCard from '../components/shared/SectionCard.vue'
import StarRating from '../components/shared/StarRating.vue'
import { useShortcuts } from '../composables/useShortcuts'
import { useToasts } from '../composables/useToasts'

/** Dev-only page that renders every shared component, for visual comparison with the design system sheet. */
useShortcuts({
  title: 'Styleguide',
  groups: [{ title: 'Move', items: [{ label: 'Next / previous item', keys: ['J', 'K'] }, { label: 'Focus search', keys: ['/'] }] }],
})
const toasts = useToasts()
const compressor = ref('off')
const accent = ref('british')
const chip = ref<string | null>('all')
const verdict = ref<Verdict>('bad')
const stars = ref(3)
const search = ref('')
const speaker = ref('all')
const filters = ref([{ key: 'flag', label: 'flag: cap_hit' }, { key: 'verdict', label: 'verdict: unjudged' }])
const confirming = ref(true)
const sample = 'data/styleguide/sample.wav'
const dotStates: DotStatus[] = ['idle', 'progress', 'picked', 'done', 'good', 'bad', 'flag']
const dotLabels: Record<DotStatus, string> = { idle: 'not started', progress: 'in progress', picked: 'picked', done: 'registered', good: 'good', bad: 'bad', flag: 'flagged' }
const abClips = computed(() => [
  { key: 'real', label: 'Real clip', sub: 'Pasqal_347.wav', path: 'data/styleguide/a.wav' },
  { key: 'bank', label: 'Bank render', sub: 'voxcpm2', path: 'data/styleguide/b.wav' },
  { key: 'raw', label: 'Raw clone', sub: 'c0 · seed 4821', path: 'data/styleguide/c.wav' },
  { key: 'fx', label: 'Clone + FX', sub: 'no FX selected', path: null },
])
</script>

<template>
  <div class="page">
    <div class="page-head"><h1 class="page-title">Styleguide</h1><span class="page-sub">every shared component · dev only</span></div>

    <div class="grid">
      <section class="blk">
        <h2>Buttons</h2>
        <div class="wrap">
          <Btn variant="primary" kbd="P">Register pick</Btn><Btn kbd="S">Save profile</Btn><Btn variant="ghost">Cancel</Btn><Btn variant="danger" kbd="R">Reject</Btn><Btn variant="good">Accept</Btn>
          <Btn icon label="Move up"><span aria-hidden="true">↑</span></Btn>
        </div>
        <div class="wrap"><Btn variant="primary" size="lg" kbd="⌘↵">Generate 6 takes</Btn><Btn size="sm">Small</Btn><Btn disabled>Disabled</Btn><Btn class="is-focus">Focused</Btn></div>
        <h2>Judging pair</h2>
        <JudgePair v-model="verdict" />
      </section>
      <section class="blk">
        <h2>Segmented and chips</h2>
        <Seg v-model="compressor" aria-label="Compressor" :options="[{ value: 'off', label: 'Off' }, { value: 'mild', label: 'Mild' }, { value: 'strong', label: 'Strong' }]" />
        <Seg v-model="accent" accent aria-label="Accent" :options="[{ value: 'british', label: 'British' }, { value: 'american', label: 'American' }, { value: 'other', label: 'Other' }]" />
        <FilterChips v-model="chip" aria-label="Emotion" :options="[{ value: 'all', label: 'All', count: 79 }, { value: 'neutral', label: 'neutral', count: 41 }, { value: 'amused', label: 'amused', count: 8 }, { value: 'sad', label: 'sad', count: 5 }]" />
        <div class="wrap"><Tag variant="real">real</Tag><Tag variant="designed">designed</Tag><Tag variant="slot">slot</Tag><Tag variant="bank">bank</Tag><Tag variant="nobank">no bank</Tag></div>
      </section>
      <section class="blk">
        <h2>Flags, scores, dots, stars</h2>
        <div class="wrap"><Flag>cap_hit</Flag><Flag>slow 3.1 c/s</Flag><Flag tone="bad">ASR WER 0.42</Flag><Flag tone="info">too_long</Flag></div>
        <div class="wrap"><ScoreChip tone="ok">p_us 0.00</ScoreChip><ScoreChip tone="hot">p_us 0.96</ScoreChip><ScoreChip>australia 0.98</ScoreChip><ScoreChip tone="none">unscored</ScoreChip></div>
        <div class="wrap"><span v-for="d in dotStates" :key="d" class="wrap"><StatusDot :status="d" :label="dotLabels[d]" />{{ dotLabels[d] }}</span></div>
        <StarRating v-model="stars" />
      </section>
    </div>

    <section class="blk">
      <h2>Filter bar</h2>
      <FilterBar>
        <SearchField v-model="search" class="grow" placeholder="Search line text" />
        <SelectField v-model="speaker" label="Speaker" :options="[{ value: 'all', label: 'All' }, { value: 'x', label: 'Ruoldo' }]" />
      </FilterBar>
      <ActiveFilters :filters="filters" :shown="412" :total="11051" @remove="(k) => (filters = filters.filter((f) => f.key !== k))" @clear="filters = []" />
    </section>

    <div class="grid">
      <section class="blk">
        <h2>Rows with status dots</h2>
        <div class="vs-card rows">
          <div class="list-head">Needs a voice <span class="n">20</span></div>
          <DataRow as="a" href="#" selected><template #lead><StatusDot status="progress" label="in progress" /></template><b>Governor Ruoldo</b><template #end><span class="num muted">79</span></template></DataRow>
          <DataRow as="a" href="#"><template #lead><StatusDot status="idle" label="not started" /></template><b>High Factotum Janris Danrok</b><template #end><span class="num muted">498</span></template></DataRow>
          <DataRow><template #lead><InlinePlay :id="sample" /></template>Oh! Yes! Yes, of course, this very day…<template #meta><Tag>surprised 0.4</Tag><span class="num muted">2.4 s</span></template></DataRow>
        </div>
      </section>
      <section class="blk">
        <h2>Collapsible sections</h2>
        <SectionCard title="Options" step="3" collapsed-by-default summary="cfg 2 · 10 steps · new seed per line">Body</SectionCard>
        <SectionCard title="Post-processing" step="4" summary="2 presets"><div class="wrap"><Tag variant="designed">1 · v4 Machine</Tag><Tag variant="designed">2 · Cavernous</Tag></div></SectionCard>
      </section>
    </div>

    <div class="grid">
      <section class="blk">
        <h2>Toasts and saves</h2>
        <Toast action-label="Undo" action-key="Z">Merged <b>Male eldar</b> into <b>Male human</b> · 55 lines moved</Toast>
        <Toast kind="err" action-label="Retry">Verdict not saved: 503 from /api/qa. Kept locally, will retry.</Toast>
        <SavedIndicator ago="2 s ago" />
        <div class="wrap"><Btn size="sm" @click="toasts.undo('Merged a into b', () => toasts.ok('Undone'))">Fire undo toast</Btn><Btn size="sm" @click="toasts.error('Could not save', () => toasts.ok('Retried'))">Fire error toast</Btn></div>
      </section>
      <section class="blk">
        <h2>Inline error and confirm</h2>
        <InlineError title="File not found"><div class="mono dim">data/voices/ruoldo_ref.wav</div><div class="muted">Check the path is relative to the repo root.</div></InlineError>
        <InlineConfirm v-if="confirming" confirm-label="Merge" @confirm="confirming = false" @cancel="confirming = false">Merge <b>Male eldar</b> into <b>Male human</b>? <b>55 lines</b> move; the slot is removed.</InlineConfirm>
        <Btn v-else size="sm" @click="confirming = true">Show confirm again</Btn>
      </section>
      <section class="blk">
        <h2>Busy and loading</h2>
        <BusyJobCard title="Generating take 3 of 6" :elapsed-s="7" :eta-s="21" :progress="0.42" detail="“I am most flattered by your attention…”" cancelable />
        <Skeleton :rows="3" />
      </section>
    </div>

    <div class="grid">
      <section class="blk">
        <h2>Inline play</h2>
        <div class="wrap"><InlinePlay :id="sample" /><InlinePlay :id="null" unavailable-reason="No render" /><InlinePlay :id="sample" large /></div>
        <InlinePlay :id="sample" waveform />
      </section>
      <section class="blk wide">
        <h2>A/B compare strip</h2>
        <ABCompareStrip :clips="abClips" line="I am a bit tipsy, so I cannot help it!" hotkeys />
      </section>
    </div>

    <section class="blk"><h2>Audio bar</h2><AudioBar static /></section>

    <div class="grid">
      <section class="blk"><h2>Empty / loading / error</h2>
        <EmptyState title="Nothing matches these filters" message="412 clips are hidden by 2 filters."><Btn size="sm">Clear filters</Btn></EmptyState>
        <EmptyState state="loading" title="Loading 11,051 clips" message="Reading merged export…" />
        <EmptyState state="error" title="Could not reach the API" message="Check the studio server is running." />
      </section>
    </div>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: var(--s-4); }
.blk { display: flex; flex-direction: column; gap: var(--s-3); padding: var(--s-5); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); min-width: 0; }
.wide { grid-column: span 2; }
h2 { margin: 0; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); font-weight: 600; }
.wrap { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.rows { padding: 4px; }
@media (max-width: 700px) { .wide { grid-column: auto; } }
</style>
