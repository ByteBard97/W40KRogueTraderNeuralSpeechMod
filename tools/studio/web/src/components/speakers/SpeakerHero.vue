<script setup lang="ts">
import { computed } from 'vue'
import type { Counts, SpeakerRow } from '../../utils/speakerRows'
import { blurAfterPointer } from '../../utils/keys'
import Btn from '../ui/Btn.vue'
import SpeakerProgress from './SpeakerProgress.vue'

const props = defineProps<{ counts: Counts; next: SpeakerRow | null; picks: number; busy: boolean }>()
const emit = defineEmits<{ continue: []; register: [] }>()

/** Drop focus after a mouse click so Enter confirms the inline question instead of re-pressing this button. */
function onRegister(e: MouseEvent) {
  blurAfterPointer(e)
  emit('register')
}

const summary = computed(() => {
  const c = props.counts
  return `${c.total} speakers · ${c.needVoice} need a voice · ${c.haveSource} have a source · ${c.picked} picked, ${c.registered} registered`
})
</script>

<template>
  <div class="hero vs-card">
    <div class="title">
      <h1 class="page-title">Speakers</h1>
      <span class="page-sub">{{ summary }}</span>
    </div>
    <SpeakerProgress class="prog" :counts="counts" />
    <div class="acts">
      <Btn variant="primary" size="lg" kbd="N" :disabled="!next" data-continue @click="emit('continue')">
        {{ next ? `Continue: ${next.speaker.name}` : 'All speakers started' }}
      </Btn>
      <Btn size="lg" data-register-all :disabled="busy || !picks" :title="picks ? undefined : 'Nothing is picked yet'" @click="onRegister">Register all picks</Btn>
    </div>
  </div>
</template>

<style scoped>
.hero { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-4) var(--s-5); padding: var(--s-4) 20px; }
.title { display: flex; flex-direction: column; gap: var(--s-1); min-width: 0; }
.prog { flex: 1 1 260px; }
.acts { display: flex; flex-wrap: wrap; gap: var(--s-2); margin-left: auto; }
@media (max-width: 640px) { .acts { margin-left: 0; } }
</style>
