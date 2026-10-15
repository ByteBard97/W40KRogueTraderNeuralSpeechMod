<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Bg3Voice, CastAudition, CastCharacter, LabelDef } from '../../api/types'
import { fileUrl } from '../../utils/fileUrl'
import { filterVoices, filtersForCharacter, labelSummary, type LabelFilters, type VoiceSort } from '../../utils/castVoices'
import Btn from '../ui/Btn.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import LabelFilter from '../voices/LabelFilter.vue'
import SearchField from '../ui/SearchField.vue'
import Seg from '../ui/Seg.vue'
import Tag from '../ui/Tag.vue'

type Tab = 'suggested' | 'all'
const ALL_LIMIT = 600     // every catalog voice, so an A to Z list is complete

/** BG3 voices to cast the character as: the server's suggestions first (big voices for big characters), or every voice. */
const props = defineProps<{
  character: CastCharacter
  voices: Bg3Voice[]
  auditions: Record<string, CastAudition>
  auditioning: string | null
  schema: LabelDef[]
}>()
const emit = defineEmits<{ assign: [slug: string]; audition: [slug: string] }>()

const tab = ref<Tab>('suggested')
const q = ref('')
const labels = ref<LabelFilters>({})
const sort = ref<VoiceSort>('lines')
const bySlug = computed(() => new Map(props.voices.map((v) => [v.slug, v])))
const suggested = computed(() => props.character.suggestions.map((s) => bySlug.value.get(s.slug)).filter((v): v is Bg3Voice => !!v))
const filtersOn = computed(() => Object.values(labels.value).some((v) => v.length))
const all = computed(() => filterVoices(props.voices, q.value, 'all', sort.value, labels.value).slice(0, ALL_LIMIT))
const matchCharacter = () => { labels.value = filtersForCharacter(props.character); tab.value = 'all' }
/** Any active label filter searches every voice; otherwise the tab decides. */
const rows = computed(() => (tab.value === 'suggested' && !filtersOn.value ? suggested.value : all.value))
const key = (v: Bg3Voice) => `${props.character.speaker}|${v.slug}`
/** Every other character this voice is already cast as (the biggest first). */
const others = (v: Bg3Voice) => v.used_by.filter((s) => s !== props.character.speaker)
const isCast = (v: Bg3Voice) => props.character.assignment?.bg3 === v.slug
const SORTS = [{ value: 'lines' as VoiceSort, label: 'Most lines' }, { value: 'name' as VoiceSort, label: 'A to Z' }]
const OPTIONS = [{ value: 'suggested' as Tab, label: 'Suggested' }, { value: 'all' as Tab, label: 'All BG3 voices' }]
</script>

<template>
  <section class="voices">
    <header class="bar">
      <Seg v-model="tab" :options="OPTIONS" aria-label="Which voices to show" />
      <template v-if="tab === 'all'">
        <SearchField v-model="q" placeholder="Find a BG3 voice" label="Find a BG3 voice" :focus-key="false" />
        <Seg v-model="sort" :options="SORTS" aria-label="Sort BG3 voices" />
      </template>
      <Btn size="sm" :title="'Filter to the labels that fit this character (gender and age)'" @click="matchCharacter">Match this character</Btn>
      <span v-if="tab === 'all' || filtersOn" class="count">{{ all.length }} voices</span>
    </header>
    <LabelFilter v-model="labels" :schema="schema" />
    <p v-if="!rows.length" class="empty">No voices to show.</p>
    <ul v-else class="list">
      <li v-for="v in rows" :key="v.slug" class="vrow" :class="{ cast: isCast(v) }">
        <InlinePlay :id="v.refs[0].wav" :src="fileUrl(v.refs[0].wav)" :title="v.name" subtitle="reference clip" />
        <div class="id">
          <b>{{ v.name }}</b><span v-if="v.aliases?.length" class="alias">also {{ v.aliases.join(', ') }}</span>
          <span class="meta">{{ v.lines.toLocaleString() }} lines · {{ v.gender }}<template v-if="v.f0"> · {{ Math.round(v.f0) }} Hz</template><template v-if="v.refs[0].speech_seconds"> · {{ Math.round(v.refs[0].speech_seconds) }} s of speech</template><template v-if="labelSummary(v)"> · {{ labelSummary(v) }}</template></span>
        </div>
        <Tag v-if="others(v).length" variant="slot" :title="others(v).join(', ')">{{ isCast(v) ? 'shared with' : 'cast as' }} {{ others(v).join(', ') }}</Tag>
        <Tag v-if="v.non_human">creature</Tag>
        <Tag v-if="v.quality === 'poor'" :title="'Less than 8 seconds of clean speech in the best reference clip'">short reference</Tag>
        <Tag v-else-if="v.refs[0].kind === 'stitched'" :title="'Reference built from several short lines by the same speaker'">stitched ref</Tag>
        <div class="acts">
          <InlinePlay v-if="auditions[key(v)]" :id="auditions[key(v)].file" :src="fileUrl(auditions[key(v)].file)" title="Audition" subtitle="their line, this voice" />
          <Btn size="sm" :disabled="auditioning !== null" @click="emit('audition', v.slug)">{{ auditioning === key(v) ? 'Generating…' : 'Audition' }}</Btn>
          <Btn size="sm" :variant="isCast(v) ? 'good' : 'primary'" @click="emit('assign', v.slug)">{{ isCast(v) ? 'Cast' : 'Cast as this' }}</Btn>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.voices { display: flex; flex-direction: column; gap: var(--s-3); }
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3); }
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.vrow { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); padding: var(--s-2) var(--s-3); border-top: 1px solid var(--line); }
.vrow.cast { background: var(--selected); border-radius: var(--r-md); }
.id { display: flex; flex-direction: column; min-width: 140px; flex: 1 1 180px; }
.id b { color: var(--text); }
.meta { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); }
.acts { display: flex; align-items: center; gap: var(--s-2); margin-left: auto; }
.empty { color: var(--text-3); }
.alias { font-size: var(--fs-xs); color: var(--text-3); }
.count { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); }
</style>
