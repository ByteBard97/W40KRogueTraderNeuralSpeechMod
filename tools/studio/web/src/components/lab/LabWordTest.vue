<script setup lang="ts">
import { computed } from 'vue'
import { useWordTest } from '../../composables/useWordTest'
import { useModelStore } from '../../stores/model'
import SectionCard from '../shared/SectionCard.vue'
import Btn from '../ui/Btn.vue'
import InlineError from '../ui/InlineError.vue'
import RealClips from './RealClips.vue'
import LabTakeCard, { type BoardEntry } from './LabTakeCard.vue'

const MODES = ['arpabet', 'plain', 'literal'] as const
const t = useWordTest()
const model = useModelStore()
const entries = computed(() => t.results.value.map((r) => ({ label: r.label, error: r.error, entry: r.take ? ({ id: r.take.id, title: r.label, wav: r.take.wav, seed: r.take.seed, metrics: r.take.metrics, pieces: r.take.pieces } satisfies BoardEntry) : null })))
</script>

<template>
  <SectionCard title="Word test" collapsed-by-default summary="one word, several pronunciations, same seed">
    <div class="form">
      <label class="field"><span class="lbl">Word or phrase</span><input v-model="t.word.value" data-word /></label>
      <label class="field"><span class="lbl">Carrier sentence</span><input v-model="t.carrier.value" data-carrier /></label>
      <p v-if="!t.carrier.value.includes('{w}')" class="muted hint" data-carrier-warn>The carrier needs <code>{w}</code> where the word goes.</p>
      <table class="tbl" data-variants>
        <thead><tr><th>Mode</th><th>Value (blank = no override)</th><th /></tr></thead>
        <tbody>
          <tr v-for="v in t.variants.value" :key="v.id" data-variant>
            <td><select v-model="v.mode" aria-label="Mode"><option v-for="m in MODES" :key="m" :value="m">{{ m }}</option></select></td>
            <td><input v-model="v.value" class="val mono" aria-label="Value" /></td>
            <td><Btn size="sm" variant="ghost" icon label="Remove variant" @click="t.removeVariant(v.id)">×</Btn></td>
          </tr>
        </tbody>
      </table>
      <div class="row">
        <Btn size="sm" data-add-variant @click="t.addVariant()">Add variant</Btn>
        <Btn variant="primary" data-run-word :disabled="!t.canRun.value || model.state === 'down'" @click="t.run()">Render {{ t.variants.value.length }} variants</Btn>
        <span v-if="t.running.value" class="num" data-word-progress>{{ t.progress.value.done }}/{{ t.progress.value.total }}</span>
      </div>
      <InlineError v-if="t.error.value" title="Word test failed"><div>{{ t.error.value }}</div></InlineError>
    </div>
    <RealClips :word="t.word.value" />
    <div class="board">
      <template v-for="r in entries" :key="r.label">
        <LabTakeCard v-if="r.entry" :entry="r.entry" :ab-slot="null" />
        <InlineError v-else title="Variant failed"><div data-variant-error>{{ r.label }}: {{ r.error }}</div></InlineError>
      </template>
    </div>
  </SectionCard>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: var(--s-2); align-items: flex-start; }
.form .field { width: 100%; max-width: 560px; }
.val { width: 100%; }
.row { display: flex; gap: var(--s-2); align-items: center; flex-wrap: wrap; }
.hint { margin: 0; font-size: var(--fs-sm); }
.board { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--s-3); margin-top: var(--s-3); }
</style>
