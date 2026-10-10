<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import type { FxPresetInfo } from '../../api/types'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import SectionCard from '../shared/SectionCard.vue'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import Tag from '../ui/Tag.vue'

const DEFAULT_FAMILY = 'Presets'
const ctx = useSpeakerContext()
const library = ref<FxPresetInfo[]>([])

// The library carries family and version when the server is new enough; otherwise fall back to the plain names.
onMounted(async () => {
  try {
    library.value = await api.fxLibrary()
  } catch {
    library.value = []
  }
})
const presets = computed<FxPresetInfo[]>(() =>
  library.value.length ? library.value : ctx.fxAvailable.value.map((name) => ({ name, source: 'scenario', dsp: '', notes: '' })),
)
const info = (name: string) => presets.value.find((p) => p.name === name)
const groups = computed(() => {
  const g = new Map<string, FxPresetInfo[]>()
  for (const p of presets.value) if (!ctx.fxChosen.value.includes(p.name)) g.set(p.family ?? DEFAULT_FAMILY, [...(g.get(p.family ?? DEFAULT_FAMILY) ?? []), p])
  return [...g.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})
const available = computed(() => groups.value.reduce((n, [, l]) => n + l.length, 0))
const summary = computed(() => (ctx.fxChosen.value.length ? 'Runs in this order on the raw clone' : 'No FX · takes stay raw'))
const showVersion = (v?: string) => (v && v !== 'v1' ? v : '')

function onPick(e: Event) {
  const el = e.target as HTMLSelectElement
  add(el.value)
  el.value = ''      // the placeholder stays selected, ready for the next preset
}
function add(name: string) {
  if (name && !ctx.fxChosen.value.includes(name)) ctx.fxChosen.value = [...ctx.fxChosen.value, name]
}
const remove = (name: string) => (ctx.fxChosen.value = ctx.fxChosen.value.filter((n) => n !== name))
</script>

<template>
  <SectionCard title="Post-processing" step="4" :summary="summary">
    <template #actions><RouterLink to="/fx" class="lab">Open in FX Lab ↗</RouterLink></template>
    <div class="body">
      <div class="chain">
        <button v-for="(n, i) in ctx.fxChosen.value" :key="n" type="button" class="chip" :data-fx="n" :aria-label="`Remove ${n} (step ${i + 1})`" @click="remove(n)">
          <span class="num">{{ i + 1 }}</span>{{ n }}<Tag v-if="showVersion(info(n)?.version)">{{ info(n)?.version }}</Tag><Icon name="x" :size="10" />
        </button>
        <label class="field add">
          <span class="lbl">Add</span>
          <select aria-label="Add a preset to the chain" :disabled="!available" @change="onPick">
            <option value="">{{ available ? `Search ${available} presets…` : 'No presets to add' }}</option>
            <optgroup v-for="[family, list] in groups" :key="family" :label="family">
              <option v-for="p in list" :key="p.name" :value="p.name">{{ p.name }}{{ showVersion(p.version) ? ` (${p.version})` : '' }}</option>
            </optgroup>
          </select>
        </label>
      </div>
      <span class="muted note">Real clips are often already processed; FX on a clone from one may be applied twice.</span>
    </div>
  </SectionCard>
</template>

<style scoped>
.body { display: flex; flex-direction: column; gap: var(--s-2); }
.chain { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 6px; min-height: 28px; padding: 0 10px; border-radius: var(--r-pill); border: 1px solid var(--selected-line); background: var(--accent-tint); color: var(--accent-hi); font-size: 13px; cursor: pointer; }
.chip .num { font-size: var(--fs-xs); color: var(--accent); }
.chip:hover { border-color: var(--bad-line); color: var(--text); }
.add { min-width: 240px; }
.add select { color: var(--text); }
.lab { font-size: var(--fs-sm); color: var(--text-2); text-decoration: none; padding: 0 var(--s-2); }
.lab:hover { color: var(--text); }
.note { font-size: var(--fs-sm); }
</style>
