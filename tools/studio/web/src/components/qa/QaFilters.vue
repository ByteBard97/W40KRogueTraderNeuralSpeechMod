<script setup lang="ts">
import { reactive } from 'vue'
import type { QaFacets, QaFilter, QaSort } from '../../api/types'

defineProps<{ facets: QaFacets }>()
const emit = defineEmits<{ change: [filter: QaFilter] }>()

const SORTS: QaSort[] = ['suspicious', 'slowest', 'fastest', 'longest', 'shortest', 'random']
const f = reactive({ speaker: '', ref: '', engine: '', flag: '', verdict: '', q: '', sort: 'suspicious' as QaSort })
const fire = () => emit('change', { ...f })
</script>

<template>
  <div class="filters">
    <select v-model="f.speaker" data-speaker @change="fire">
      <option value="">all speakers</option>
      <option v-for="s in facets.speakers" :key="s" :value="s">{{ s }}</option>
    </select>
    <select v-model="f.ref" data-ref @change="fire">
      <option value="">all references</option>
      <option v-for="r in facets.refs" :key="r" :value="r">{{ r }}</option>
    </select>
    <select v-model="f.engine" data-engine @change="fire">
      <option value="">all engines</option>
      <option v-for="e in facets.engines" :key="e" :value="e">{{ e }}</option>
    </select>
    <select v-model="f.flag" data-flag @change="fire">
      <option value="">any flags</option>
      <option value="any flag">has a flag</option>
      <option value="no flag">no flag</option>
      <option v-for="g in facets.flags" :key="g" :value="g">{{ g }}</option>
    </select>
    <select v-model="f.verdict" data-verdict @change="fire">
      <option value="">any verdict</option>
      <option value="unjudged">unjudged</option>
      <option value="good">good</option>
      <option value="bad">bad</option>
    </select>
    <select v-model="f.sort" data-sort @change="fire">
      <option v-for="s in SORTS" :key="s" :value="s">sort: {{ s }}</option>
    </select>
    <input v-model="f.q" data-q placeholder="search the line text" @change="fire" />
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
</style>
