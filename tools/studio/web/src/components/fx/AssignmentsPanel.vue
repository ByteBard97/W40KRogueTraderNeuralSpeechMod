<script setup lang="ts">
import type { FxPreview, FxWritten } from '../../api/types'

defineProps<{ preview: FxPreview | null; written: FxWritten | null }>()
const emit = defineEmits<{ preview: []; write: [] }>()
</script>

<template>
  <div>
    <p class="dim">Expands the label map and your active speaker profiles into the file the FX batch reads. Nothing is written until you press Write.</p>
    <button data-preview @click="emit('preview')">Preview</button>
    <template v-if="preview">
      <p>{{ preview.lines }} lines and {{ preview.speakers }} speakers would get FX.</p>
      <p v-for="(n, label) in preview.unmapped_labels" :key="label" class="warn">{{ n }} lines use “{{ label }}”, which has no preset yet.</p>
      <p v-for="s in preview.sample" :key="s.guid" class="dim">{{ s.guid.slice(0, 8) }} → {{ s.presets.join(' + ') }}</p>
      <button data-write class="primary" @click="emit('write')">Write assignments.json</button>
    </template>
    <p v-if="written" class="ok">Wrote {{ written.path }} ({{ written.lines }} lines, {{ written.speakers }} speakers). The previous file is kept as .bak.</p>
  </div>
</template>

<style scoped>
.primary { background: var(--acc); color: #0b1220; border-color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
.warn { color: #f0b400; font-size: 13px; }
.ok { color: var(--ok); }
</style>
