<script setup lang="ts">
import { useLabStore } from '../../stores/lab'

const lab = useLabStore()
const stageLabel = (n: string) => n.replace(/_/g, ' ')
</script>

<template>
  <section class="pipe vs-card" aria-label="Pipeline preview">
    <h2 class="list-head">Pipeline preview <span v-if="lab.preparing" class="spinner" aria-label="Preparing" /></h2>
    <p v-if="!lab.prepared" class="muted pad">Select a line to see what the model receives.</p>
    <template v-else>
      <div class="stages">
        <label v-for="s in lab.prepared.stages" :key="s.name" class="stage" data-stage>
          <span class="lbl">{{ stageLabel(s.name) }}</span>
          <textarea class="field" readonly rows="2" :value="s.text" />
        </label>
      </div>
      <h3 class="sub">Pieces sent to the model ({{ lab.prepared.pieces.length }})</h3>
      <ol class="pieces">
        <template v-for="(p, i) in lab.prepared.pieces" :key="i">
          <li class="chip" data-piece><span class="kind">{{ p.kind }}</span><span class="txt">{{ p.display || p.text }}</span></li>
          <li v-if="p.gap_ms" class="gap num" data-gap aria-label="silence">⏸ {{ p.gap_ms }} ms</li>
        </template>
      </ol>
    </template>
  </section>
</template>

<style scoped>
.pipe { padding-bottom: var(--s-3); min-width: 0; }
.pad { padding: 0 var(--s-3); }
.stages { display: flex; flex-direction: column; gap: var(--s-2); padding: 0 var(--s-3); }
.stage { display: flex; flex-direction: column; gap: 2px; }
.stage .lbl { color: var(--text-3); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.06em; }
.stage textarea { min-height: 44px; font-size: 13px; background: var(--inset); }
.sub { margin: var(--s-3) var(--s-3) var(--s-1); font-size: var(--fs-sm); color: var(--text-2); }
.pieces { list-style: none; margin: 0; padding: 0 var(--s-3); display: flex; flex-direction: column; gap: var(--s-1); }
.chip { display: flex; gap: var(--s-2); align-items: baseline; padding: var(--s-1) var(--s-2); background: var(--raised); border: 1px solid var(--line-strong); border-radius: var(--r-md); font-size: 13px; }
.kind { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--accent); flex: none; }
.gap { align-self: center; font-size: var(--fs-xs); color: var(--info); border-top: 1px dashed var(--info-line); padding-top: 2px; width: 100%; text-align: center; }
</style>
