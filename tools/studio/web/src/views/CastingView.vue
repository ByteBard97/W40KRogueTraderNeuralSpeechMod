<script setup lang="ts">
import { computed, onMounted } from 'vue'
import CastQueue from '../components/casting/CastQueue.vue'
import CharacterPanel from '../components/casting/CharacterPanel.vue'
import VoiceList from '../components/casting/VoiceList.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import Btn from '../components/ui/Btn.vue'
import InlineError from '../components/ui/InlineError.vue'
import SearchField from '../components/ui/SearchField.vue'
import Seg from '../components/ui/Seg.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { useToasts } from '../composables/useToasts'
import { api } from '../api/client'
import { useCastingStore, type CastFilter, type CastKind } from '../stores/casting'

const cast = useCastingStore()
const toasts = useToasts()
onMounted(() => cast.load())

const FILTERS = [{ value: 'open' as CastFilter, label: 'No voice yet' }, { value: 'cast' as CastFilter, label: 'Cast' }, { value: 'all' as CastFilter, label: 'All' }]
const KINDS = [{ value: 'character' as CastKind, label: 'Characters' }, { value: 'slot' as CastKind, label: 'Nameless groups' }, { value: 'all' as CastKind, label: 'Both' }]
const firstLoad = computed(() => cast.loading && !cast.page)
const portraits = computed(() => cast.page?.portraits ?? [])

async function assign(slug: string) {
  const who = cast.current?.speaker
  if (!who) return
  await cast.assign(who, slug)
  if (!cast.error) cast.nextOpen()
}

async function register() {
  try {
    const r = await api.castRegister()
    toasts.ok(`Registered ${r.registered.length} voices in the prompt bank${r.skipped.length ? `, ${r.skipped.length} skipped` : ''}`)
  } catch (e) {
    toasts.error(e instanceof Error ? e.message : String(e))
  }
}
</script>

<template>
  <div class="page casting">
    <div class="page-head">
      <div class="titles">
        <h1 class="page-title">Casting</h1>
        <span class="page-sub">Give each character without a voice a real BG3 voice. Biggest characters first, so the best voices go where they are heard most.</span>
      </div>
      <div class="progress">
        <b>{{ cast.counts.assigned }}</b> of {{ cast.counts.total }} cast · {{ cast.linesLeft.toLocaleString() }} lines still without a cast voice
        <Btn size="sm" variant="primary" :disabled="!cast.counts.assigned" @click="register">Register cast voices</Btn>
      </div>
    </div>

    <InlineError v-if="cast.error" title="Casting problem"> {{ cast.error }} <Btn size="sm" @click="cast.load()">Retry</Btn></InlineError>

    <Skeleton v-if="firstLoad" :rows="6" />
    <div v-else-if="cast.page" class="split">
      <div class="side">
        <div class="filters">
          <Seg v-model="cast.kind" :options="KINDS" aria-label="Named characters or nameless groups" />
          <Seg v-model="cast.filter" :options="FILTERS" aria-label="Which characters to show" />
          <SearchField v-model="cast.query" placeholder="Find a character" label="Find a character" />
        </div>
        <EmptyState v-if="!cast.visible.length" message="No characters for this filter." />
        <CastQueue v-else :rows="cast.visible" :selected="cast.current?.speaker ?? null" @select="cast.select" />
      </div>
      <div v-if="cast.current" class="main">
        <CharacterPanel :character="cast.current" :portraits="portraits" @clear="cast.assign(cast.current.speaker, null)"
          @portrait="cast.setPortrait(cast.current.speaker, $event)" />
        <VoiceList :character="cast.current" :voices="cast.voices" :auditions="cast.auditions" :auditioning="cast.auditioning" :schema="cast.schema"
          @assign="assign" @audition="cast.audition(cast.current.speaker, $event)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.titles { display: flex; flex-direction: column; gap: var(--s-1); flex: 1 1 360px; min-width: 0; }
.progress { margin-left: auto; display: flex; align-items: center; gap: var(--s-3); flex-wrap: wrap; color: var(--text-2); }
.filters { display: flex; flex-direction: column; gap: var(--s-2); }
.side { max-width: 400px; }
@media (max-width: 480px) { .progress { margin-left: 0; } .side { max-width: none; flex-basis: 100%; } }
</style>
