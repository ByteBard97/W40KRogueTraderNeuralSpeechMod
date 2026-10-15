<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import MonitorPanel from '../components/pedalboard/MonitorPanel.vue'
import Palette from '../components/pedalboard/Palette.vue'
import PedalboardCanvas from '../components/pedalboard/PedalboardCanvas.vue'
import PresetBar from '../components/pedalboard/PresetBar.vue'
import { useGraphEngine, type EngineControl } from '../composables/useGraphEngine'
import { usePedalboardStore } from '../stores/pedalboard'
import DemoShell from './DemoShell.vue'
import DemoTransport from './DemoTransport.vue'
import GraphFileBar from './GraphFileBar.vue'
import { makeDemoNode } from './faustLoader'
import { fileStem, GraphFileError, parseGraphFile, serializeGraph } from './graphIo'
import { useDemoAudio } from './useDemoAudio'

// Waits for a burst of edits (dropping a pedal, then wiring it) to settle so the compiler runs once.
const RECOMPILE_DEBOUNCE_MS = 300

const store = usePedalboardStore()
const engine = useGraphEngine({ makeNode: makeDemoNode })
const audio = useDemoAudio(engine)

const canvas = ref<InstanceType<typeof PedalboardCanvas> | null>(null)
const gap = ref(0)
const graphName = ref('')
const fileMessage = ref('')
let timer: ReturnType<typeof setTimeout> | undefined

function recompile() {
  const c = store.compileNow()
  if (c) void engine.compile(c.code, c.controls as EngineControl[], c.params)
}
watch(() => store.structuralRev, () => {
  clearTimeout(timer)
  timer = setTimeout(recompile, RECOMPILE_DEBOUNCE_MS)
})
watch(() => store.graph.name, (n) => (graphName.value = n), { immediate: true })
const stopLive = store.onLive((c) => engine.setParam(c.key, c.value))

function setGap(seconds: number) {
  gap.value = seconds
  engine.setGap(seconds)
}

async function save(name: string) {
  const res = await store.save(name)
  fileMessage.value = res ? `Saved ${res.name} in this browser.` : store.error ?? ''
}

function download(text: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
function exportGraph() {
  download(serializeGraph(store.graph), `${fileStem(store.graph.name)}.json`, 'application/json')
}
function exportFaust() {
  const c = store.compileNow()
  if (!c) { fileMessage.value = 'Fix the wiring first: the graph does not make a program yet.'; return }
  download(c.code, `${fileStem(store.graph.name)}.dsp`, 'text/plain')
}
async function importGraph(file: File) {
  try {
    store.loadGraph(parseGraphFile(await file.text(), store.catalog))
    fileMessage.value = `Loaded ${file.name}.`
  } catch (e) {
    fileMessage.value = e instanceof GraphFileError ? e.message : `Could not read ${file.name}.`
  }
}

const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(t.tagName))
function onKey(e: KeyboardEvent) {
  if (e.key !== ' ' || typing(e.target) || !audio.sourceName.value) return
  e.preventDefault()
  if (engine.playing.value) engine.stop()
  else engine.play()
}

onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await store.load()
  if (store.error) fileMessage.value = store.error
  // Start from a working chain so the first sound already shows what a graph does.
  const first = store.starters.find((s) => s.slug === 'clean') ?? store.starters[0]
  if (first) store.loadStarter(first.slug)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  clearTimeout(timer)
  stopLive()
  engine.dispose()
})
</script>

<template>
  <DemoShell>
    <div class="page pedalboard">
      <header class="page-head">
        <h1 class="page-title">Voice Pedalboard</h1>
        <p class="lede">
          Drop effect pedals on a canvas, wire them in any order, and hear a voice clip run through the result while you turn the knobs.
          The wiring becomes one Faust program that compiles right here in the page.
        </p>
      </header>
      <p class="privacy" data-testid="privacy">Nothing is uploaded. Your audio, your microphone and your saved graphs stay in this browser.</p>
      <details class="how" data-testid="how-it-works">
        <summary>How it works</summary>
        <ol>
          <li>Each pedal is a small Faust function. The wires you draw are joined into a single Faust program, which FaustWasm compiles in your browser and plays through Web Audio.</li>
          <li>Knobs change values in the running program. Rewiring or adding a pedal compiles a new program and crossfades from the old one over 50 milliseconds.</li>
          <li>The monitor shows the output spectrum and left/right statistics. Load a reference voice and its average spectrum is drawn as a dashed line to aim at.</li>
          <li>Export Faust program saves the generated code as a plain .dsp file.</li>
        </ol>
        <p>
          Patching Faust blocks visually is not new: Faust Playground, FaustWave and FaustMod already do it. What this adds is that the same generated program can be reproduced by a batch renderer
          (the project this came from renders whole voice banks that way), the reference overlay, and the crossfade when you rewire.
          Known limits: the first compile of a big graph takes a second or two, and parallel branches with different delays can comb-filter where they merge.
        </p>
        <p>Third-party licenses are listed in <a href="THIRD_PARTY_NOTICES.md">THIRD_PARTY_NOTICES.md</a>.</p>
      </details>
      <DemoTransport
        :playing="engine.playing.value"
        :bypass="engine.bypassRaw.value"
        :gap="gap"
        :source="audio.sourceName.value"
        :reference-name="audio.referenceName.value"
        :recording="audio.recording.value"
        :record-left="audio.recordLeft.value"
        @test-signal="audio.useTestSignal()"
        @file="audio.useFile($event)"
        @record="audio.record()"
        @reference="audio.chooseReference($event)"
        @play="engine.play()"
        @stop="engine.stop()"
        @bypass="engine.setBypassRaw($event)"
        @gap="setGap"
      />
      <p v-if="audio.notice.value" class="alert" role="alert" data-testid="audio-notice">{{ audio.notice.value }}</p>
      <PresetBar
        v-model:name="graphName"
        :starters="store.starters"
        :saved="store.savedNames"
        :dirty="store.dirty"
        :valid="store.valid"
        :issues="store.issueTexts"
        :saving="store.saving"
        :can-undo="store.undoCount > 0"
        :can-redo="store.redoCount > 0"
        @load-starter="store.loadStarter($event)"
        @load-saved="store.loadSaved($event)"
        @save="save"
        @new="store.newGraph()"
        @undo="store.undo()"
        @redo="store.redo()"
      />
      <GraphFileBar :message="fileMessage" @export="exportGraph" @export-faust="exportFaust" @import="importGraph" />
      <p v-if="engine.status.value === 'error'" class="alert" role="alert" data-testid="engine-error">{{ engine.error.value }}</p>
      <div class="board">
        <Palette :blocks="store.catalog.blocks" @add="canvas?.addAtCenter($event)" />
        <PedalboardCanvas ref="canvas" />
      </div>
      <p class="legend">Every wire carries left and right. Stereo pedals make the two sides differ; watch the Stereo panel.</p>
      <MonitorPanel :taps="engine.taps" :reference="audio.reference.value" :running="engine.playing.value" />
    </div>
  </DemoShell>
</template>

<style scoped>
.pedalboard { max-width: none; }
.lede { margin: 0; flex: 1 1 420px; color: var(--text-2); font-size: var(--fs-md); max-width: 70ch; }
.privacy { margin: 0; color: var(--text-3); font-size: var(--fs-sm); }
.how { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); padding: var(--s-2) var(--s-3); color: var(--text-2); font-size: var(--fs-sm); }
.how summary { cursor: pointer; font-weight: 600; color: var(--text); }
.how p, .how ol { max-width: 80ch; }
.board { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: var(--s-3); height: 72vh; min-height: 520px; }
.board > :first-child { min-height: 0; }
.legend { margin: 0; color: var(--text-3); font-size: var(--fs-sm); }
.alert { margin: 0; padding: var(--s-2) var(--s-3); border: 1px solid var(--bad-line); background: var(--bad-tint); border-radius: var(--r-md); color: var(--text-2); font-family: var(--font-mono); font-size: var(--fs-sm); white-space: pre-wrap; }
@media (max-width: 760px) { .board { grid-template-columns: 1fr; height: auto; } .board > :last-child { height: 60vh; } }
</style>
