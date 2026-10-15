<script setup lang="ts">
defineProps<{ message: string }>()
const emit = defineEmits<{ export: []; 'export-faust': []; import: [file: File] }>()
const pick = (e: Event) => {
  const el = e.target as HTMLInputElement
  const f = el.files?.[0]
  if (f) emit('import', f)
  el.value = ''
}
</script>

<template>
  <div class="bar">
    <button type="button" class="btn" data-testid="export-graph" title="Download this graph as a JSON file" @click="emit('export')">Export graph</button>
    <label class="btn file">Import graph<input type="file" accept="application/json,.json" data-testid="import-graph" @change="pick"></label>
    <button type="button" class="btn" data-testid="export-faust" title="Download the generated Faust program" @click="emit('export-faust')">Export Faust program</button>
    <span v-if="message" class="msg" role="status" data-testid="graph-message">{{ message }}</span>
  </div>
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); }
.btn { display: inline-flex; align-items: center; min-height: var(--hit); padding: 0 var(--s-3); border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); font-size: var(--fs-md); font-weight: 500; cursor: pointer; }
.btn:hover { background: var(--inset); }
.file { position: relative; }
.file input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.file:focus-within { outline: 2px solid var(--focus); outline-offset: 2px; }
.msg { color: var(--warn); font-size: var(--fs-sm); }
</style>
