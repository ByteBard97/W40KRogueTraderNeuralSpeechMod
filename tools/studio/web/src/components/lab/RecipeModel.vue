<script setup lang="ts">
import { computed } from 'vue'
import { useLabStore } from '../../stores/lab'
import { MAX_SEEDS, MIN_SEEDS } from '../../utils/labRecipe'
import Seg from '../ui/Seg.vue'

const CFG_MIN = 1
const CFG_MAX = 4
const CFG_STEP = 0.1
const STEPS_MIN = 4
const STEPS_MAX = 30
const INSTRUCTS = [{ value: 'annotation' as const, label: 'annotation' }, { value: 'none' as const, label: 'none' }, { value: 'custom' as const, label: 'custom' }]

const props = defineProps<{ seedCount: number }>()
const emit = defineEmits<{ 'update:seedCount': [n: number] }>()
const lab = useLabStore()
const r = computed(() => lab.recipe!)

/** Blank number boxes mean "off" (null) for the optional fields. */
const nullable = (key: 'retry_ratio' | 'peak_limit_db') => (e: Event) => {
  const v = (e.target as HTMLInputElement).value
  r.value[key] = v === '' ? null : Number(v)
}
</script>

<template>
  <div class="grid">
    <label class="field wide"><span class="lbl">cfg</span>
      <input v-model.number="r.cfg" type="range" :min="CFG_MIN" :max="CFG_MAX" :step="CFG_STEP" aria-label="cfg slider" />
      <input v-model.number="r.cfg" class="num" type="number" :min="CFG_MIN" :max="CFG_MAX" :step="CFG_STEP" aria-label="cfg" data-cfg />
    </label>
    <label class="field"><span class="lbl">steps</span><input v-model.number="r.timesteps" class="num" type="number" :min="STEPS_MIN" :max="STEPS_MAX" data-steps /></label>
    <label class="field"><span class="lbl">seed</span><input v-model="r.seed" class="num" inputmode="numeric" placeholder="random" data-seed /></label>
    <label class="field"><span class="lbl">seeds per item</span>
      <input class="num" type="number" :min="MIN_SEEDS" :max="MAX_SEEDS" :value="props.seedCount" data-seed-count @input="emit('update:seedCount', Number(($event.target as HTMLInputElement).value))" />
    </label>
    <label class="field"><span class="lbl">retry ratio</span><input class="num" type="number" step="0.1" :value="r.retry_ratio ?? ''" placeholder="default" @input="nullable('retry_ratio')($event)" /></label>
    <label class="field"><span class="lbl">peak limit dB</span><input class="num" type="number" step="0.5" :value="r.peak_limit_db ?? ''" placeholder="off" @input="nullable('peak_limit_db')($event)" /></label>
    <label class="check"><input v-model="r.retry_badcase" type="checkbox" /> retry bad case</label>
    <label class="check"><input v-model="r.normalize" type="checkbox" /> normalize</label>
    <label class="check"><input v-model="r.clean" type="checkbox" /> clean game markup</label>
  </div>
  <fieldset class="style">
    <legend>Style prefix</legend>
    <Seg v-model="r.instruct" :options="INSTRUCTS" aria-label="Style prefix" />
    <textarea v-if="r.instruct === 'custom'" v-model="r.instruct_text" class="field" rows="2" placeholder="Custom style text" data-instruct-text />
    <p class="muted hint" data-line-instruct>
      This line's own instruct: <em>{{ lab.selected?.instruct || 'none' }}</em>
      <template v-if="r.instruct === 'annotation'"> (sent)</template>
    </p>
  </fieldset>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: var(--s-2); align-items: center; }
.wide { grid-column: 1 / -1; }
.field input[type="range"] { flex: 1 1 auto; accent-color: var(--accent); }
.field input.num { width: 7ch; flex: none; }
.check { display: inline-flex; gap: var(--s-2); align-items: center; min-height: var(--hit); }
.style { border: 1px solid var(--line); border-radius: var(--r-md); margin: var(--s-3) 0 0; padding: var(--s-2) var(--s-3); display: flex; flex-direction: column; gap: var(--s-2); }
.style legend { color: var(--text-3); font-size: var(--fs-sm); padding: 0 var(--s-1); }
.hint { margin: 0; font-size: var(--fs-sm); }
</style>
