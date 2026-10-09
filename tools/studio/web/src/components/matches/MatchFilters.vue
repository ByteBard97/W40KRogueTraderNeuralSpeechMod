<script setup lang="ts">
import { reactive } from 'vue'
import type { MatchFilter } from '../../api/types'

const emit = defineEmits<{ change: [filter: MatchFilter] }>()
const f = reactive({ group: '', speaker: '', state: '', q: '' })
const fire = () => emit('change', { ...f })
</script>

<template>
  <div class="filters">
    <select v-model="f.group" data-group @change="fire">
      <option value="">all groups</option>
      <option value="flagged">flagged</option>
      <option value="bank">clean, has a voice bank</option>
      <option value="nobank">clean, no bank</option>
    </select>
    <select v-model="f.state" data-state @change="fire">
      <option value="">any decision</option>
      <option value="undecided">undecided</option>
      <option value="accept">accepted</option>
      <option value="reject">rejected</option>
    </select>
    <input v-model="f.speaker" data-speaker placeholder="proposed speaker" @change="fire" />
    <input v-model="f.q" data-q placeholder="search names and lines" @change="fire" />
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
</style>
