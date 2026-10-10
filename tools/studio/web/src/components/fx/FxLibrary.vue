<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FxPresetInfo } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import SearchField from '../ui/SearchField.vue'
import Tag from '../ui/Tag.vue'
import { fxPreviewId, fxRenderUrl } from './previewUrl'

const FALLBACK_FAMILY = 'Other'
const FALLBACK_VERSION = 'v1'
const props = defineProps<{ presets: FxPresetInfo[] }>()
const q = ref('')

const families = computed(() => {
  const needle = q.value.trim().toLowerCase()
  const groups = new Map<string, FxPresetInfo[]>()
  for (const p of props.presets) {
    if (needle && !`${p.name} ${p.notes}`.toLowerCase().includes(needle)) continue
    const f = p.family || FALLBACK_FAMILY
    groups.set(f, [...(groups.get(f) ?? []), p])
  }
  return [...groups].map(([name, items]) => ({ name, items }))
})
const shown = computed(() => families.value.reduce((n, f) => n + f.items.length, 0))
</script>

<template>
  <section class="section" aria-labelledby="lib-h">
    <div class="section-head">
      <h2 id="lib-h" class="section-title">Preset library</h2>
      <span class="num muted">{{ q ? `${shown} of ${presets.length}` : presets.length }}</span>
    </div>
    <div class="search"><SearchField v-model="q" label="Search presets" placeholder="Search presets" /></div>
    <EmptyState v-if="!presets.length" message="No presets found." />
    <EmptyState v-else-if="!shown" message="No preset matches that search." />
    <div class="list">
      <template v-for="f in families" :key="f.name">
        <div class="fam">{{ f.name }} <span class="num n">{{ f.items.length }}</span></div>
        <div v-for="p in f.items" :key="p.name" class="pre" data-preset :title="p.notes || undefined">
          <InlinePlay
            :id="fxPreviewId([p.name])"
            :src="fxRenderUrl([p.name])"
            :title="`Preview · ${p.name}`"
            subtitle="Default sample"
          />
          <span class="nm">{{ p.name }}</span>
          <Tag>{{ p.version || FALLBACK_VERSION }}</Tag>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.section { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); }
.section-head { display: flex; align-items: baseline; gap: var(--s-2); padding: var(--s-3) var(--s-4); }
.section-title { margin: 0; font-size: var(--fs-md); font-weight: 600; }
.search { padding: 0 var(--s-3) var(--s-2); }
.list { padding: 0 var(--s-1) var(--s-2); }
.fam { padding: 10px var(--s-3) 2px; font-size: var(--fs-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); }
.n { font-weight: 400; }
.pre { display: flex; align-items: center; gap: var(--s-2); min-height: 36px; padding: 2px var(--s-2); border-radius: var(--r-md); }
.pre:hover { background: var(--hover); }
.nm { flex: 1 1 auto; min-width: 0; font-size: var(--fs-md); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
