<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api } from '../../api/client'
import type { SpotSample } from '../../api/types'
import { usePoolsStore } from '../../stores/pools'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'
import Btn from '../ui/Btn.vue'
import InlineError from '../ui/InlineError.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import Seg from '../ui/Seg.vue'

type Mark = 'right' | 'wrong' | ''
const MARKS = [{ value: 'right' as Mark, label: 'Right' }, { value: 'wrong' as Mark, label: 'Wrong' }]

/** Ten sampled lines from one slot: is each one the right kind of voice? Keys Y W (J K move) are driven by the page. */
const props = defineProps<{ slotId: string; slotName: string }>()
const pools = usePoolsStore()
const sample = ref<SpotSample | null>(null)
const marks = reactive<Record<string, Mark>>({})
const cursor = ref(0)
const error = ref('')
const submitting = ref(false)

const items = computed(() => sample.value?.items ?? [])
const marked = computed(() => items.value.filter((i) => marks[i.guid]).length)
const wrong = computed(() => items.value.filter((i) => marks[i.guid] === 'wrong').length)
const complete = computed(() => items.value.length > 0 && marked.value === items.value.length)
const left = computed(() => items.value.length - marked.value)
const note = computed(() => (complete.value ? `${wrong.value} wrong of ${items.value.length}` : `${left.value} left · ${wrong.value} wrong so far`))

async function load() {
  error.value = ''
  try {
    sample.value = await api.poolSpot(props.slotId)
    for (const k of Object.keys(marks)) delete marks[k]
    cursor.value = 0
  } catch (e) {
    sample.value = null
    error.value = e instanceof Error ? e.message : String(e)
  }
}
async function submit() {
  if (!complete.value || submitting.value) return
  submitting.value = true
  const results = Object.fromEntries(items.value.map((i) => [i.guid, marks[i.guid] === 'right']))
  const r = await pools.recordSpot(props.slotId, results)
  submitting.value = false
  if (r) await load()
}
/** Mark the line under the cursor and move on to the next unmarked one. */
function mark(value: 'right' | 'wrong') {
  const i = items.value[cursor.value]
  if (!i) return
  marks[i.guid] = value
  const next = items.value.findIndex((x, n) => n > cursor.value && !marks[x.guid])
  if (next >= 0) cursor.value = next
}
const step = (delta: number) => (cursor.value = Math.min(Math.max(0, cursor.value + delta), Math.max(0, items.value.length - 1)))
const title = (t: string) => (t.length > 60 ? `${t.slice(0, 60)}…` : t)

watch(() => props.slotId, load, { immediate: true })
defineExpose({ mark, step, submit })
</script>

<template>
  <SectionCard id="spot" :title="`Spot check · ${slotName}`" :summary="`${marked} / ${items.length} marked`">
    <InlineError v-if="error" title="Could not load a sample">{{ error }}</InlineError>
    <EmptyState v-else-if="sample && !items.length" message="Nothing left to check in this slot." />
    <div v-for="(i, n) in items" :key="i.guid" class="sc" :class="{ cur: n === cursor }" :aria-current="n === cursor ? 'true' : undefined" @pointerdown="cursor = n">
      <div class="line">
        <InlinePlay class="pl" :id="i.wav ?? null" :title="title(i.text)" :subtitle="`Spot check · ${slotName}`" unavailable-reason="This line is not rendered yet" />
        <span class="t">{{ i.text }}</span>
      </div>
      <Seg :model-value="marks[i.guid] ?? ''" :options="MARKS" aria-label="Is this the right slot?" @update:model-value="(v) => (marks[i.guid] = v as Mark)" />
    </div>
    <p v-if="items.length" class="hint">Y right · W wrong · J K next, previous{{ sample && sample.remaining > items.length ? ` · ${sample.remaining - items.length} more unchecked in this slot` : '' }}</p>
    <div v-if="items.length" class="foot">
      <Btn variant="primary" data-submit :disabled="!complete || submitting" @click="submit">Submit spot check</Btn>
      <span class="note">{{ note }}</span>
    </div>
  </SectionCard>
</template>

<style scoped>
.sc { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--s-3); align-items: center; padding: var(--s-2) 0; border-top: 1px solid var(--line); }
.sc.cur { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); padding-inline: var(--s-2); border-top-color: transparent; }
.line { display: flex; gap: var(--s-2); align-items: flex-start; min-width: 0; }
.pl { flex: none; }
.t { font-size: 13px; line-height: 1.4; padding-top: 6px; }
.hint { margin: var(--s-3) 0 0; font-size: 13px; color: var(--text-3); }
.foot { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; padding-top: var(--s-3); }
.note { font-size: var(--fs-sm); color: var(--text-3); }
</style>
