<script setup lang="ts">
import { computed } from 'vue'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { SEED_POLICY_OPTIONS, SEED_POLICY_SUMMARY } from '../../utils/seedPolicy'
import SectionCard from '../shared/SectionCard.vue'
import Seg from '../ui/Seg.vue'

const ctx = useSpeakerContext()
const o = ctx.options
const onOff = (v: boolean) => (v ? 'on' : 'off')
const summary = computed(() => {
  const seed = ctx.seedPolicy.value === 'fixed' && o.value.seed.trim() ? `fixed seed ${o.value.seed.trim()}` : SEED_POLICY_SUMMARY[ctx.seedPolicy.value]
  return `cfg ${o.value.cfg} · ${o.value.timesteps} steps · ${seed} · style prefix ${onOff(o.value.use_instruct)} · retry ${onOff(o.value.retry_badcase)} · normalise ${onOff(o.value.normalize)} · continuation ${onOff(o.value.continuation)}`
})
</script>

<template>
  <SectionCard title="Options" step="3" collapsed-by-default :summary="summary">
    <div class="body">
      <div class="row">
        <label class="field w-num"><span class="lbl">cfg</span><input v-model.number="o.cfg" data-cfg type="number" step="0.5" /></label>
        <label class="field w-steps"><span class="lbl">Timesteps</span><input v-model.number="o.timesteps" data-timesteps type="number" /></label>
        <Seg v-model="ctx.seedPolicy.value" :options="[...SEED_POLICY_OPTIONS]" aria-label="Seed policy" />
        <label v-if="ctx.seedPolicy.value === 'fixed'" class="field w-seed"><span class="lbl">Seed</span><input v-model="o.seed" data-seed placeholder="e.g. 4821" /></label>
      </div>
      <p class="muted note">
        {{ ctx.seedPolicy.value === 'new' ? 'Every line gets its own random seed.' : ctx.seedPolicy.value === 'one' ? 'One random seed is drawn for the whole batch.' : 'The typed seed is used for every line.' }}
        Ticked sources share the seed of a line, so a difference between them comes from the clip.
      </p>
      <div class="checks">
        <label><input v-model="o.use_instruct" type="checkbox" />Use the line's style annotation as a prefix</label>
        <label><input v-model="o.retry_badcase" type="checkbox" />Retry bad takes</label>
        <label><input v-model="o.normalize" type="checkbox" />Normalise text</label>
      </div>
      <details>
        <summary class="muted">Advanced</summary>
        <label class="adv"><input v-model="o.continuation" data-continuation type="checkbox" />Continuation: also pass the transcript as a prompt <span class="muted">· can echo the reference audio at the start; the bank was rendered with it off</span></label>
      </details>
    </div>
  </SectionCard>
</template>

<style scoped>
.body { display: flex; flex-direction: column; gap: var(--s-3); }
.row { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.w-num { width: 110px; }
.w-steps { width: 150px; }
.w-seed { width: 170px; }
.note { margin: 0; font-size: var(--fs-sm); }
.checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%), 1fr)); gap: var(--s-2); }
label { display: flex; gap: var(--s-2); align-items: center; }
.field { display: inline-flex; }
input[type='checkbox'] { accent-color: var(--accent); }
summary { cursor: pointer; font-size: 13px; }
.adv { padding-top: var(--s-2); }
.adv span { font-size: var(--fs-sm); }
</style>
