<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useDesign } from '../../composables/useDesign'
import { useDesignGeneration } from '../../composables/useGeneration'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { useWorkbenchAction } from '../../composables/useWorkbenchActions'
import { useLiveTakesStore } from '../../stores/liveTakes'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import InlinePlay from '../ui/InlinePlay.vue'

const DEFAULT_CFG = 2
const DEFAULT_STEPS = 10
const takeFile = (file: string) => `data/voice_design/${file}`

const props = defineProps<{ description: string }>()
const ctx = useSpeakerContext()
const design = useDesign()
const gen = useDesignGeneration()
const liveStore = useLiveTakesStore()

const open = ref(false)
const seed = ref('')
const cfg = ref(DEFAULT_CFG)
const steps = ref(DEFAULT_STEPS)
const takes = design.liveTakes
const newest = computed(() => takes.value[0] ?? null)
const reason = computed(() => (!props.description.trim() ? 'Write a description first.' : gen.blocked.value))
watch(() => takes.value.length, (n) => { if (n) open.value = true })

function generate() {
  if (reason.value) return
  open.value = true
  void gen.generate({ description: props.description, seed: seed.value, cfg: cfg.value, timesteps: steps.value }, (t) => liveStore.add(ctx.slug, t))
}
useWorkbenchAction('generate-design', generate)
</script>

<template>
  <section class="live" :data-open="open">
    <button type="button" class="head" :aria-expanded="open" @click="open = !open">
      <Icon name="chev" :size="14" class="chev" />
      <b>Live design</b>
      <span class="muted sum">Generate another candidate from the description · seed {{ seed.trim() || 'random' }} · cfg {{ cfg }} · {{ steps }} steps</span>
    </button>
    <div v-if="open" class="body">
      <div class="row">
        <label class="field w-seed"><span class="lbl">Seed</span><input v-model="seed" data-seed placeholder="random" /></label>
        <label class="field w-num"><span class="lbl">cfg</span><input v-model.number="cfg" type="number" step="0.5" /></label>
        <label class="field w-num"><span class="lbl">Steps</span><input v-model.number="steps" type="number" /></label>
        <Btn variant="primary" data-generate :disabled="!!reason || gen.busy.value" :title="reason" kbd="G" @click="generate">{{ gen.busy.value ? 'Generating…' : 'Generate' }}</Btn>
        <Btn data-keep-newest :disabled="!newest" @click="newest && design.keep(newest)">Keep as {{ design.nextId.value }}</Btn>
      </div>
      <p v-if="reason" class="muted note">{{ reason }}</p>
      <p v-if="gen.busy.value" class="muted note">Runs in the background. The take appears here when it is done.</p>
      <div v-for="t in takes" :key="t.file" class="take">
        <InlinePlay :id="takeFile(t.file)" :title="`${ctx.detail.value?.summary.name ?? ''} · unkept take`" :subtitle="t.file" />
        <button type="button" class="seedchip num" data-seed-chip title="Use this seed again" @click="seed = String(t.seed)">seed {{ t.seed }}</button>
        <span class="muted num">cfg {{ t.cfg }} · {{ t.timesteps }} steps · {{ t.seconds }} s</span>
        <Btn size="sm" data-keep @click="design.keep(t)">Keep as {{ design.nextId.value }}</Btn>
      </div>
    </div>
  </section>
</template>

<style scoped>
.live { border: 1px solid var(--line); border-radius: var(--r-lg); background: var(--raised); }
.head { display: flex; align-items: center; gap: var(--s-2); width: 100%; min-height: var(--hit-lg); padding: 0 var(--s-3); background: transparent; border: 0; color: var(--text); text-align: left; cursor: pointer; }
.sum { font-size: var(--fs-sm); font-weight: 400; }
.chev { color: var(--text-3); transition: transform 0.15s; flex: none; }
[data-open="true"] .chev { transform: rotate(90deg); }
.body { display: flex; flex-direction: column; gap: var(--s-2); padding: 0 var(--s-3) var(--s-3); }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); }
.w-seed { width: 150px; }
.w-num { width: 110px; }
.note { margin: 0; font-size: var(--fs-sm); }
.take { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); font-size: var(--fs-sm); }
.seedchip { background: var(--accent-tint); color: var(--accent-hi); border: 1px solid var(--selected-line); border-radius: var(--r-pill); padding: 0 10px; min-height: 24px; font-size: var(--fs-sm); cursor: pointer; }
</style>
