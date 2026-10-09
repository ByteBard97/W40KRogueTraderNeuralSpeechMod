<script setup lang="ts">
import { useSpeakerContext } from '../../composables/useSpeakerContext'

const ctx = useSpeakerContext()
</script>

<template>
  <div class="grid">
    <label>cfg <input data-cfg type="number" step="0.5" v-model.number="ctx.options.value.cfg" /></label>
    <label>timesteps <input data-timesteps type="number" v-model.number="ctx.options.value.timesteps" /></label>
    <label>seed <input data-seed v-model="ctx.options.value.seed" placeholder="blank = new random per line" /> <span class="dim">a typed value pins every line</span></label>
    <label><input type="checkbox" v-model="ctx.options.value.use_instruct" /> use the line's annotation style as a prefix</label>
    <label><input type="checkbox" v-model="ctx.options.value.retry_badcase" /> retry bad takes</label>
    <label><input type="checkbox" v-model="ctx.options.value.normalize" /> normalize text</label>
    <label><input data-continuation type="checkbox" v-model="ctx.options.value.continuation" /> continuation: also pass the transcript as a prompt</label>
  </div>
  <p class="dim">Continuation can echo the reference audio at the start of the output; the bank was rendered with it off. One seed is used per line and shared by every ticked source.</p>
</template>

<style scoped>
.grid { display: grid; gap: 6px; }
label { display: flex; gap: 8px; align-items: center; }
.dim { color: var(--dim); font-size: 12px; }
</style>
