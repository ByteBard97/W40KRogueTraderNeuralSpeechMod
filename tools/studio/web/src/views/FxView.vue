<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AssignmentsPreview from '../components/fx/AssignmentsPreview.vue'
import FxLabFrame from '../components/fx/FxLabFrame.vue'
import FxLibrary from '../components/fx/FxLibrary.vue'
import LabelMap from '../components/fx/LabelMap.vue'
import Btn from '../components/ui/Btn.vue'
import Flag from '../components/ui/Flag.vue'
import InlineConfirm from '../components/ui/InlineConfirm.vue'
import InlineError from '../components/ui/InlineError.vue'
import { useShortcuts } from '../composables/useShortcuts'
import { useToasts } from '../composables/useToasts'
import { useFxStore } from '../stores/fx'

const fx = useFxStore()
const route = useRoute()
const toasts = useToasts()
const confirming = ref(false)
const notice = ref('')

const clip = computed(() => (typeof route.query.clip === 'string' ? route.query.clip : undefined))
const dirty = computed(() => fx.dirtyCount > 0)
const sub = computed(() => `Which effect presets apply to which voice label · ${fx.library.length} presets · ${fx.labelNames.length} labels`)
const affected = computed(() => fx.diff?.changed)

useShortcuts({
  title: 'FX',
  groups: [
    { title: 'Label map', items: [{ label: 'Write map…', keys: ['Ctrl', 'S'] }, { label: 'Confirm write', keys: ['↵'] }, { label: 'Cancel', keys: ['Esc'] }, { label: 'Reorder a chip', keys: ['Alt', '←', '→'] }] },
    { title: 'Library', items: [{ label: 'Search presets', keys: ['/'] }] },
  ],
})

function askWrite() {
  if (dirty.value || fx.diff?.changed) confirming.value = true
}
function onKey(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault()
    askWrite()
  }
}
onMounted(() => {
  document.addEventListener('keydown', onKey)
  void fx.load()
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

function discard() {
  fx.discard()
  confirming.value = false
}
async function doWrite() {
  confirming.value = false
  const w = await fx.writeMap()
  if (!w) return
  const done = `Wrote assignments.json (${w.lines} lines, ${w.speakers} speakers)`
  const backup = w.backup
  if (backup) toasts.undo(`${done}. Previous file kept as ${backup}`, () => void fx.restore(backup).then((r) => r && toasts.ok(`Restored ${r.restored}`)))
  else toasts.ok(`${done}. There was no earlier file to back up.`)
}
async function onPresetSaved(name: string) {
  notice.value = `Saved preset “${name}” in the FX Lab.`
  await fx.reloadLibrary()
}
</script>

<template>
  <div class="page fx">
    <div class="page-head">
      <div class="titles"><h1 class="page-title">FX</h1><span class="page-sub">{{ sub }}</span></div>
      <div class="actions">
        <template v-if="dirty">
          <Flag>{{ fx.dirtyCount }} unsaved {{ fx.dirtyCount === 1 ? 'change' : 'changes' }}</Flag>
          <Btn variant="ghost" data-discard @click="discard">Discard</Btn>
        </template>
        <span v-else class="saved">Map matches the file on disk</span>
        <Btn variant="primary" kbd="Ctrl S" data-write :disabled="(!dirty && !affected) || fx.writing" @click="askWrite">Write map…</Btn>
      </div>
    </div>

    <InlineError v-if="fx.error" title="The FX service said no">{{ fx.error }}</InlineError>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>

    <InlineConfirm v-if="confirming" confirm-label="Write" @confirm="doWrite" @cancel="confirming = false">
      Write <b>{{ dirty ? `${fx.dirtyCount} label ${fx.dirtyCount === 1 ? 'change' : 'changes'}` : 'the map' }}</b> to <span class="mono">fx_labels.json</span> and expand it into
      <span class="mono">assignments.json</span>? Both current files are kept as timestamped <span class="mono">.bak.json</span> copies.
      <template v-if="affected !== undefined"> {{ affected }} {{ affected === 1 ? 'voice changes' : 'voices change' }} on the saved map (see preview).</template>
    </InlineConfirm>

    <div class="split">
      <aside class="side"><FxLibrary :presets="fx.library" /></aside>
      <div class="main">
        <LabelMap
          :draft="fx.draft"
          :labels="fx.labelNames"
          :dirty="fx.dirtyLabels"
          :presets="fx.library"
          :usage="fx.usage"
          @add="fx.add"
          @remove="fx.remove"
          @move="fx.move"
        />
        <AssignmentsPreview :diff="fx.diff" :fallback="fx.preview" :unsaved-labels="fx.dirtyCount" />
      </div>
    </div>

    <FxLabFrame :clip="clip" @preset-saved="onPresetSaved" @notice="notice = $event" />
  </div>
</template>

<style scoped>
.fx { display: flex; flex-direction: column; gap: var(--s-4); }
.titles { display: flex; flex-direction: column; gap: var(--s-1); }
.actions { margin-left: auto; display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); }
.side { max-width: 360px; }
.notice { margin: 0; color: var(--good); font-size: var(--fs-md); }
</style>
