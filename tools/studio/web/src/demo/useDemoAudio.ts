// Everything the demo does to get a voice into the engine without a server: test signal, file, microphone,
// and an optional reference clip analysed in the browser.
import { ref } from 'vue'
import type { ReferenceData } from '../api/referenceApi'
import type { useGraphEngine } from '../composables/useGraphEngine'
import { analyseReference } from './analyse'
import { makeTestSignal } from './testSignal'

export const RECORD_SECONDS = 6
const TEST_SAMPLE_RATE = 48000
const DECODE_RATE = 44100

type Engine = ReturnType<typeof useGraphEngine>

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export function useDemoAudio(engine: Engine) {
  const sourceName = ref('')
  const referenceName = ref('')
  const reference = ref<ReferenceData | null>(null)
  const recording = ref(false)
  const recordLeft = ref(0)
  const notice = ref('')

  async function start(label: string, load: () => Promise<void>) {
    try {
      await load()
      sourceName.value = label
      notice.value = ''
      engine.play()
    } catch (e) {
      notice.value = `Could not use ${label}: ${msg(e)}`
    }
  }

  const useTestSignal = () => start('built-in test signal', async () => {
    const data = makeTestSignal(TEST_SAMPLE_RATE)
    const buf = new AudioBuffer({ length: data.length, sampleRate: TEST_SAMPLE_RATE, numberOfChannels: 1 })
    buf.copyToChannel(data, 0)
    await engine.loadClip(buf)
  })

  const useFile = (file: File) => start(file.name, async () => engine.loadClip(await file.arrayBuffer()))

  async function record() {
    if (recording.value) return
    notice.value = ''
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      notice.value = `Microphone unavailable: ${msg(e)}`
      return
    }
    const chunks: Blob[] = []
    const rec = new MediaRecorder(stream)
    rec.ondataavailable = (ev) => chunks.push(ev.data)
    recording.value = true
    recordLeft.value = RECORD_SECONDS
    const tick = setInterval(() => { recordLeft.value = Math.max(0, recordLeft.value - 1) }, 1000)
    rec.onstop = () => {
      clearInterval(tick)
      stream.getTracks().forEach((t) => t.stop())
      recording.value = false
      void start('microphone recording', async () => engine.loadClip(await new Blob(chunks, { type: rec.mimeType }).arrayBuffer()))
    }
    rec.start()
    setTimeout(() => { if (rec.state !== 'inactive') rec.stop() }, RECORD_SECONDS * 1000)
  }

  async function chooseReference(file: File | null) {
    if (!file) { reference.value = null; referenceName.value = ''; return }
    try {
      const audio = await new OfflineAudioContext(1, 1, DECODE_RATE).decodeAudioData(await file.arrayBuffer())
      const channels = Array.from({ length: Math.min(2, audio.numberOfChannels) }, (_, i) => audio.getChannelData(i))
      reference.value = analyseReference(file.name, channels, audio.sampleRate)
      referenceName.value = file.name
      notice.value = ''
    } catch (e) {
      notice.value = `Could not read the reference voice: ${msg(e)}`
    }
  }

  return { sourceName, referenceName, reference, recording, recordLeft, notice, useTestSignal, useFile, record, chooseReference }
}
