<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import SectionCard from '../components/shared/SectionCard.vue'
import AssignmentsPanel from '../components/fx/AssignmentsPanel.vue'
import FxLibrary from '../components/fx/FxLibrary.vue'
import LabelMap from '../components/fx/LabelMap.vue'
import { fxLabUrl, useFxBridge } from '../composables/useFxBridge'
import { useFxStore } from '../stores/fx'
import { fileUrl } from '../utils/fileUrl'

const fx = useFxStore()
const route = useRoute()
const iframe = ref<HTMLIFrameElement | null>(null)
const notice = ref('')

const { sendClip } = useFxBridge({
  iframe,
  onPresetSaved: async (name) => {
    notice.value = `Saved preset “${name}” in the FX Lab.`
    await fx.load()
  },
})

/** A take sent here with ?clip=<repo path>: fetch its bytes (the FX Lab cannot read our files) and hand them over. */
async function sendRequestedClip() {
  const clip = route.query.clip
  if (typeof clip !== 'string' || !clip) return
  try {
    const res = await fetch(fileUrl(clip))
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    sendClip(clip.split('/').pop() ?? clip, await res.arrayBuffer())
  } catch {
    notice.value = 'Could not load that clip into the FX Lab.'
  }
}
onMounted(fx.load)
</script>

<template>
  <div>
    <h1>FX</h1>
    <p v-if="fx.error" class="err">{{ fx.error }}</p>
    <p v-if="notice" class="ok">{{ notice }}</p>
    <SectionCard title="1. FX Lab (author presets)">
      <iframe ref="iframe" class="lab" allow="autoplay" :src="fxLabUrl()" title="FX Lab" @load="sendRequestedClip" />
      <p class="dim">Needs the FX Lab server on port 8908 (<code>python3 tools/fx_lab/server.py</code>).</p>
    </SectionCard>
    <SectionCard title="2. Preset library"><FxLibrary :presets="fx.library" /></SectionCard>
    <SectionCard title="3. Label map (harness effect labels to presets)">
      <LabelMap :labels="fx.labels" :presets="fx.library.map((p) => p.name)" @save="fx.saveLabels" />
    </SectionCard>
    <SectionCard title="4. Assignments for the FX batch">
      <AssignmentsPanel :preview="fx.preview" :written="fx.written" @preview="fx.loadPreview" @write="fx.write" />
    </SectionCard>
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.lab { width: 100%; height: 640px; border: 1px solid var(--line); border-radius: 8px; background: #fff0; }
.err { color: var(--bad); }
.ok { color: var(--ok); }
.dim { color: var(--dim); font-size: 12px; }
</style>
