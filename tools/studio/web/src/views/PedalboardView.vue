<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ReferenceData, RefSpeaker } from '../api/referenceApi'
import { refLtas, refSpeakers } from '../api/referenceApi'
import MonitorPanel from '../components/pedalboard/MonitorPanel.vue'
import Palette from '../components/pedalboard/Palette.vue'
import PedalboardCanvas from '../components/pedalboard/PedalboardCanvas.vue'
import PresetBar from '../components/pedalboard/PresetBar.vue'
import TransportBar from '../components/pedalboard/TransportBar.vue'
import { useGraphEngine, type EngineControl } from '../composables/useGraphEngine'
import { useToasts } from '../composables/useToasts'
import { usePedalboardStore } from '../stores/pedalboard'

// Waits for a burst of edits (dropping a pedal, then wiring it) to settle so the compiler runs once.
const RECOMPILE_DEBOUNCE_MS = 300

const store = usePedalboardStore()
const engine = useGraphEngine()
const toasts = useToasts()

const canvas = ref<InstanceType<typeof PedalboardCanvas> | null>(null)
const refSpeakerList = ref<RefSpeaker[]>([])
const reference = ref<ReferenceData | null>(null)
const referenceName = ref('')
const gap = ref(0)
const graphName = ref('')
let timer: ReturnType<typeof setTimeout> | undefined

function recompile() {
  const c = store.compileNow()
  if (c) void engine.compile(c.code, c.controls as EngineControl[], c.params)
}

watch(() => store.structuralRev, () => {
  clearTimeout(timer)
  timer = setTimeout(recompile, RECOMPILE_DEBOUNCE_MS)
})
// Loading a saved graph brings its name into the field.
watch(() => store.graph.name, (n) => (graphName.value = n), { immediate: true })

const stopLive = store.onLive((c) => engine.setParam(c.key, c.value))

async function loadClip(url: string) {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    await engine.loadClip(await res.arrayBuffer())
  } catch (e) {
    toasts.error(`Could not load the clip: ${e instanceof Error ? e.message : String(e)}`)
  }
}

async function chooseReference(speaker: string) {
  referenceName.value = speaker
  reference.value = null
  if (!speaker) return
  try {
    reference.value = await refLtas(speaker)
  } catch (e) {
    toasts.error(`Could not load the game voice: ${e instanceof Error ? e.message : String(e)}`)
  }
}

function setGap(seconds: number) {
  gap.value = seconds
  engine.setGap(seconds)
}

async function save(name: string) {
  const res = await store.save(name)
  if (res) toasts.ok(`Saved ${res.name}`)
  else if (store.error) toasts.error(store.error)
}

const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(t.tagName))
function onKey(e: KeyboardEvent) {
  if (e.key !== ' ' || typing(e.target)) return
  e.preventDefault()
  if (engine.playing.value) engine.stop()
  else engine.play()
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await store.load()
  if (store.error) toasts.error(store.error)
  try { refSpeakerList.value = await refSpeakers() } catch { /* the reference is optional */ }
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  clearTimeout(timer)
  stopLive()
  engine.dispose()
})
</script>

<template>
  <div class="page pedalboard">
    <div class="page-head">
      <h1 class="page-title">Pedalboard</h1>
      <span class="page-sub">Drop pedals, wire them in any order, and listen while you turn the knobs.</span>
    </div>
    <TransportBar
      :playing="engine.playing.value"
      :ref-speakers="refSpeakerList"
      :bypass="engine.bypassRaw.value"
      :gap="gap"
      :reference="referenceName"
      @load-clip="loadClip"
      @play="engine.play()"
      @stop="engine.stop()"
      @bypass="engine.setBypassRaw($event)"
      @gap="setGap"
      @reference="chooseReference"
    />
    <PresetBar
      v-model:name="graphName"
      :starters="store.starters"
      :saved="store.savedNames"
      :dirty="store.dirty"
      :valid="store.valid"
      :issues="store.issueTexts"
      :saving="store.saving"
      @load-starter="store.loadStarter($event)"
      @load-saved="store.loadSaved($event)"
      @save="save"
      @new="store.newGraph()"
    />
    <p v-if="engine.status.value === 'error'" class="engine-error" role="alert" data-testid="engine-error">{{ engine.error.value }}</p>
    <div class="board">
      <Palette :blocks="store.catalog.blocks" @add="canvas?.addAtCenter($event)" />
      <PedalboardCanvas ref="canvas" />
    </div>
    <MonitorPanel :taps="engine.taps" :reference="reference" :running="engine.playing.value" />
  </div>
</template>

<style scoped>
/* A canvas wants the whole screen: the global .page cap (1480 px) leaves a wide monitor half empty. */
.pedalboard { max-width: none; }
.board { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: var(--s-3); height: 72vh; min-height: 520px; }
.board > :first-child { min-height: 0; }
.engine-error { margin: 0; padding: var(--s-2) var(--s-3); border: 1px solid var(--bad-line); background: var(--bad-tint); border-radius: var(--r-md); color: var(--text-2); font-family: var(--font-mono); font-size: var(--fs-sm); white-space: pre-wrap; }
</style>
