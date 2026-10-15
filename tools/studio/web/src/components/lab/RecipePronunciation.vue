<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LabLexiconHit, LabPronMode } from '../../api/labTypes'
import { useLabStore } from '../../stores/lab'
import Btn from '../ui/Btn.vue'

const MODES: LabPronMode[] = ['arpabet', 'plain', 'literal']
const lab = useLabStore()
const r = computed(() => lab.recipe!)
const q = ref('')
const hits = ref<LabLexiconHit[]>([])
const searched = ref(false)

const add = (word = '', mode: LabPronMode = 'arpabet', value = '') => r.value.pronunciation.push({ word, mode, value })
const remove = (i: number) => r.value.pronunciation.splice(i, 1)
async function search() {
  if (!q.value.trim()) return
  hits.value = await lab.lexicon(q.value.trim())
  searched.value = true
}
/** The lexicon's braced ARPAbet, or its plain respelling, becomes an override of the same word. */
const useHit = (h: LabLexiconHit) => add(h.word, 'arpabet', h.arpabet || h.as_sent.replace(/[{}]/g, '').trim())
</script>

<template>
  <div class="pron">
    <label class="check"><input v-model="r.lexicon" type="checkbox" data-lexicon /> shared lexicon on</label>
    <p class="muted hint">Overrides run first. ARPAbet looks like <code>V AH0 L AE1 N S IY0 AH0 S</code>; the digit is stress (0 none, 1 main, 2 secondary). Plain is a respelling, literal is sent as written.</p>
    <table v-if="r.pronunciation.length" class="tbl" data-pron-table>
      <thead><tr><th>Word</th><th>Mode</th><th>Value</th><th /></tr></thead>
      <tbody>
        <tr v-for="(p, i) in r.pronunciation" :key="i" data-pron-row>
          <td><input v-model="p.word" class="cell" placeholder="von Valancius" aria-label="Word" /></td>
          <td><select v-model="p.mode" class="cell" aria-label="Mode"><option v-for="m in MODES" :key="m" :value="m">{{ m }}</option></select></td>
          <td><input v-model="p.value" class="cell mono" aria-label="Value" /></td>
          <td><Btn size="sm" variant="ghost" icon label="Remove override" @click="remove(i)">×</Btn></td>
        </tr>
      </tbody>
    </table>
    <Btn size="sm" data-add-pron @click="add()">Add override</Btn>
    <form class="lex" @submit.prevent="search">
      <label class="field"><span class="lbl">Lexicon</span><input v-model="q" placeholder="look up a word" data-lex-q /></label>
      <Btn size="sm" type="submit" :disabled="!q.trim()">Search</Btn>
    </form>
    <ul v-if="hits.length" class="hits">
      <li v-for="h in hits" :key="h.word" data-lex-hit>
        <b>{{ h.word }}</b> sends <code class="mono">{{ h.as_sent }}</code>
        <span v-if="h.respell" class="muted"> ({{ h.respell }})</span>
        <Btn size="sm" @click="useHit(h)">use as override</Btn>
      </li>
    </ul>
    <p v-else-if="searched" class="muted hint">The lexicon has nothing for that word.</p>
  </div>
</template>

<style scoped>
.pron { display: flex; flex-direction: column; gap: var(--s-2); align-items: flex-start; }
.hint { margin: 0; font-size: var(--fs-sm); }
code { font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--accent-hi); }
.tbl { width: 100%; }
.cell { width: 100%; }
.check { display: inline-flex; gap: var(--s-2); align-items: center; }
.lex { display: flex; gap: var(--s-2); align-items: center; flex-wrap: wrap; }
.hits { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--s-1); width: 100%; }
.hits li { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; font-size: 13px; }
</style>
