<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'

const ctx = useSpeakerContext()
</script>

<template>
  <div class="bar">
    <button @click="ctx.saveProfile()">Save profile</button>
    <button @click="ctx.setActive()" :disabled="!ctx.detail.value?.profile" title="Copy the saved profile to active.json">Set active</button>
    <button
      v-if="ctx.detail.value?.design"
      data-register
      :disabled="!ctx.detail.value.design.pick"
      title="Copy the rank-1 candidate into the prompt bank so plan.py can use it"
      @click="ctx.registerPick()"
    >Register pick</button>
    <span class="dim">{{ ctx.detail.value?.profile ? `saved ${ctx.detail.value.profile.saved}` : 'no profile saved yet' }}</span>
    <span class="notice">{{ ctx.notice.value }}</span>
  </div>
</template>

<style scoped>
.bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.dim { color: var(--dim); font-size: 12px; }
.notice { color: var(--ok); font-size: 13px; }
</style>
