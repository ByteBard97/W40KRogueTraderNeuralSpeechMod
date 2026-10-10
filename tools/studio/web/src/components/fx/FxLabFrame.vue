<script setup lang="ts">
import { ref } from 'vue'
import { fxLabUrl, FX_LAB_PORT, useFxBridge } from '../../composables/useFxBridge'
import { fileUrl } from '../../utils/fileUrl'
import { useToasts } from '../../composables/useToasts'
import Btn from '../ui/Btn.vue'
import InlineError from '../ui/InlineError.vue'
import { useLabProbe } from './useLabProbe'

const START_COMMAND = 'python3 tools/fx_lab/server.py'
const props = defineProps<{ clip?: string }>()
const emit = defineEmits<{ presetSaved: [name: string]; notice: [message: string] }>()

const iframe = ref<HTMLIFrameElement | null>(null)
const collapsed = ref(false)
const toasts = useToasts()
const { state, retry } = useLabProbe(fxLabUrl())

const { sendClip } = useFxBridge({ iframe, onPresetSaved: (name) => emit('presetSaved', name) })

/** A take sent here with ?clip=<repo path>: fetch its bytes (the FX Lab cannot read our files) and hand them over. */
async function sendRequestedClip() {
  if (!props.clip) return
  try {
    const res = await fetch(fileUrl(props.clip))
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    sendClip(props.clip.split('/').pop() ?? props.clip, await res.arrayBuffer())
  } catch {
    emit('notice', 'Could not load that clip into the FX Lab.')
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(START_COMMAND)
    toasts.ok('Copied the start command.')
  } catch {
    toasts.error('Could not copy. Select the command and copy it by hand.')
  }
}
</script>

<template>
  <section class="lab" aria-labelledby="lab-h">
    <div class="head">
      <h2 id="lab-h" class="title">FX Lab</h2>
      <span class="muted sub">author and tune presets; saved presets appear in the library above</span>
    </div>
    <div class="frame">
      <div class="bar">
        <span class="pill" :class="state" role="status">
          <span class="led" aria-hidden="true" />
          {{ state === 'up' ? `FX Lab connected on :${FX_LAB_PORT}` : state === 'down' ? `FX Lab server not reachable on :${FX_LAB_PORT}` : 'Checking the FX Lab…' }}
        </span>
        <span class="grow" />
        <a class="open" :href="fxLabUrl()" target="_blank" rel="noopener">Open in new tab ↗</a>
        <Btn size="sm" variant="ghost" :pressed="collapsed" :label="collapsed ? 'Expand FX Lab' : 'Collapse FX Lab'" @click="collapsed = !collapsed">{{ collapsed ? 'Expand' : 'Collapse' }}</Btn>
      </div>
      <div v-show="!collapsed" class="body" :class="{ up: state === 'up' }">
        <iframe v-if="state === 'up'" ref="iframe" class="ifr" allow="autoplay" :src="fxLabUrl()" title="FX Lab" @load="sendRequestedClip" />
        <InlineError v-else-if="state === 'down'" title="The FX Lab runs as its own server" class="err">
          <div class="muted">Start it, then this panel loads automatically.</div>
          <div class="cmd">
            <code class="mono">{{ START_COMMAND }}</code>
            <Btn size="sm" @click="copy">Copy</Btn>
            <Btn size="sm" @click="retry">Retry</Btn>
          </div>
        </InlineError>
        <span v-else class="spinner" aria-hidden="true" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.lab { display: flex; flex-direction: column; gap: var(--s-2); }
.head { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s-2); }
.title { margin: 0; font-size: var(--fs-lg); font-weight: 600; }
.sub { font-size: var(--fs-sm); }
.frame { border: 1px solid var(--line-strong); border-radius: var(--r-lg); overflow: hidden; background: var(--n-1); }
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); padding: var(--s-2) var(--s-3); border-bottom: 1px solid var(--line); background: var(--n-2); }
.grow { flex: 1 1 auto; }
.open { color: var(--text-2); font-size: var(--fs-sm); text-decoration: none; padding: 0 var(--s-2); }
.open:hover { color: var(--text); }
.pill { display: inline-flex; align-items: center; gap: 6px; min-height: 26px; padding: 0 10px; border-radius: var(--r-pill); font-size: var(--fs-sm); border: 1px solid var(--line-strong); color: var(--text-2); }
.led { width: 8px; height: 8px; border-radius: 50%; background: var(--text-3); }
.pill.up .led { background: var(--good); }
.pill.down { border-color: var(--bad-line); color: var(--bad); }
.pill.down .led { background: var(--bad); border-radius: 2px; transform: rotate(45deg); }
.body { height: 520px; display: flex; align-items: center; justify-content: center; background: repeating-linear-gradient(45deg, transparent 0 12px, var(--hover) 12px 24px); }
.body.up { display: block; height: 640px; background: var(--n-1); }
.ifr { width: 100%; height: 100%; border: 0; display: block; }
.err { max-width: 520px; }
.cmd { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); margin-top: var(--s-2); }
.cmd code { padding: 4px 8px; border-radius: var(--r-sm); background: var(--n-1); color: var(--text); }
@media (max-width: 640px) { .body { height: 320px; } }
</style>
