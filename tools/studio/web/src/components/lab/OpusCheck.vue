<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../../api/client'
import type { LabOpusPreview } from '../../api/labTypes'
import { useGlobalAudio } from '../../composables/globalAudio'
import { useLabStore } from '../../stores/lab'
import Btn from '../ui/Btn.vue'
import Seg from '../ui/Seg.vue'

/** Hear the bank's Opus compression: pick which clip, click a bitrate, the decoded result plays with its size. */
const KBPS = [12, 16, 24, 32, 48]
const SOURCES = [{ value: 'original', label: 'Original' }, { value: 'latest', label: 'New (latest take)' }]
const lab = useLabStore()
const audio = useGlobalAudio()
const which = ref<'original' | 'latest'>('latest')
const busy = ref<number | null>(null)
const error = ref<string | null>(null)
const last = ref<LabOpusPreview | null>(null)
const source = computed(() => (which.value === 'original' ? lab.selected?.current?.wav : lab.takes[0]?.wav) ?? null)
const kb = (n: number) => `${(n / 1024).toFixed(0)} KB`

async function play(kbps: number) {
  if (!source.value) return
  busy.value = kbps
  error.value = null
  try {
    last.value = await api.labOpus(source.value, kbps)
    audio.play(last.value.wav, undefined, { title: `Opus ${kbps} kbps`, subtitle: `${which.value} · ${kb(last.value.opus_bytes)}` })
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <div class="opus" data-opus>
    <div class="head"><b>Compression check</b><span class="muted">plays the clip after Opus encode and decode, as the bank would store it</span></div>
    <Seg v-model="which" :options="SOURCES" aria-label="Clip to compress" />
    <div class="row">
      <Btn v-for="k in KBPS" :key="k" size="sm" :disabled="!source || busy !== null" :data-kbps="k" @click="play(k)">{{ busy === k ? '…' : `${k} kbps` }}</Btn>
    </div>
    <p v-if="last" class="muted" data-opus-result>{{ last.kbps }} kbps: {{ kb(last.opus_bytes) }} instead of {{ kb(last.source_bytes) }} ({{ last.ratio }}× smaller)</p>
    <p v-if="!source" class="muted">No clip yet for this choice.</p>
    <p v-if="error" class="err" data-opus-error>{{ error }}</p>
  </div>
</template>

<style scoped>
.opus { display: flex; flex-direction: column; gap: var(--s-2); border-top: 1px solid var(--line); padding-top: var(--s-3); }
.head { display: flex; flex-direction: column; gap: 2px; font-size: var(--fs-sm); }
.row { display: flex; flex-wrap: wrap; gap: var(--s-2); }
.err { color: var(--bad, #e57373); margin: 0; }
p { margin: 0; font-size: var(--fs-sm); }
</style>
