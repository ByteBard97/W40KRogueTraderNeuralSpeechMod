<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PedalboardStarter } from '../../api/types'

const MAX_ISSUES_SHOWN = 4
type Menu = 'starters' | 'saved' | null

const props = defineProps<{
  starters: PedalboardStarter[]
  saved: string[]
  name: string
  dirty: boolean
  valid: boolean
  issues: string[]
  saving?: boolean
  canUndo?: boolean
  canRedo?: boolean
}>()
const emit = defineEmits<{
  'update:name': [name: string]
  'load-starter': [slug: string]
  'load-saved': [name: string]
  save: [name: string]
  new: []
  undo: []
  redo: []
}>()

const open = ref<Menu>(null)
const trimmed = computed(() => props.name.trim())
const canSave = computed(() => props.valid && trimmed.value.length > 0 && !props.saving)
const categories = computed(() => {
  const names = [...new Set(props.starters.map((s) => s.category))]
  return names.map((c) => ({ name: c, items: props.starters.filter((s) => s.category === c) }))
})
const shownIssues = computed(() => props.issues.slice(0, MAX_ISSUES_SHOWN))
const hiddenIssues = computed(() => Math.max(0, props.issues.length - MAX_ISSUES_SHOWN))

function toggle(menu: Exclude<Menu, null>) {
  open.value = open.value === menu ? null : menu
}
function pickStarter(slug: string) {
  open.value = null
  emit('load-starter', slug)
}
function pickSaved(name: string) {
  open.value = null
  emit('load-saved', name)
}
function submit() {
  if (canSave.value) emit('save', trimmed.value)
}
</script>

<template>
  <div class="bar">
    <div class="menu">
      <button type="button" class="btn" data-testid="preset-starters" :aria-expanded="open === 'starters'" @click="toggle('starters')">Starting points</button>
      <div v-if="open === 'starters'" class="pop" role="menu">
        <p v-if="!starters.length" class="empty">No starting points yet.</p>
        <div v-for="c in categories" :key="c.name" class="cat">
          <span class="cat-name">{{ c.name }}</span>
          <button v-for="s in c.items" :key="s.slug" type="button" role="menuitem" class="entry" :title="s.description" :data-testid="`starter-${s.slug}`" @click="pickStarter(s.slug)">
            {{ s.name }}<span class="d">{{ s.description }}</span>
          </button>
        </div>
      </div>
    </div>
    <div class="menu">
      <button type="button" class="btn" data-testid="preset-saved" :aria-expanded="open === 'saved'" @click="toggle('saved')">My graphs</button>
      <div v-if="open === 'saved'" class="pop" role="menu">
        <p v-if="!saved.length" class="empty">Nothing saved yet.</p>
        <button v-for="n in saved" :key="n" type="button" role="menuitem" class="entry" :data-testid="`saved-${n}`" @click="pickSaved(n)">{{ n }}</button>
      </div>
    </div>
    <button type="button" class="btn" data-testid="new-btn" @click="emit('new')">New</button>
    <div class="history" role="group" aria-label="History">
      <button type="button" class="btn" data-testid="undo-btn" title="Undo (Ctrl+Z)" :disabled="!canUndo" @click="emit('undo')">Undo</button>
      <button type="button" class="btn" data-testid="redo-btn" title="Redo (Ctrl+Shift+Z)" :disabled="!canRedo" @click="emit('redo')">Redo</button>
    </div>
    <form class="save" @submit.prevent="submit">
      <input class="name" type="text" placeholder="Name this graph" aria-label="Graph name" data-testid="name-input" :value="name" maxlength="60" @input="emit('update:name', ($event.target as HTMLInputElement).value)" />
      <button type="submit" class="btn primary" data-testid="save-btn" :disabled="!canSave">Save</button>
    </form>
    <span v-if="dirty" class="dirty" data-testid="dirty" title="Changes not saved">Unsaved changes</span>
    <ul v-if="!valid && issues.length" class="issues" data-testid="issues" role="status">
      <li v-for="t in shownIssues" :key="t">{{ t }}</li>
      <li v-if="hiddenIssues" class="more">and {{ hiddenIssues }} more</li>
    </ul>
  </div>
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); padding: var(--s-2) var(--s-3); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); }
.menu { position: relative; }
.history { display: flex; gap: var(--s-1); }
.btn { min-height: var(--hit); padding: 0 var(--s-3); border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); font-size: var(--fs-md); font-weight: 500; cursor: pointer; }
.btn:hover { background: var(--inset); }
.btn:disabled { color: var(--text-off); border-color: var(--line); background: transparent; cursor: not-allowed; }
.primary:not(:disabled) { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.pop { position: absolute; z-index: var(--z-overlay); top: calc(100% + var(--s-1)); left: 0; min-width: 260px; max-height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-2); background: var(--raised); border: 1px solid var(--line-strong); border-radius: var(--r-md); box-shadow: var(--e-2); }
.cat { display: flex; flex-direction: column; }
.cat-name { padding: var(--s-1) var(--s-2); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-3); }
.entry { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; padding: var(--s-1) var(--s-2); background: transparent; border: 0; border-radius: var(--r-sm); color: var(--text); font-size: var(--fs-md); text-align: left; cursor: pointer; }
.entry:hover { background: var(--hover); }
.d { color: var(--text-3); font-size: var(--fs-xs); }
.empty { margin: 0; padding: var(--s-2); color: var(--text-3); font-size: var(--fs-sm); }
.save { display: flex; gap: var(--s-2); margin-left: auto; }
.name { background: var(--inset); color: var(--text); border: 1px solid var(--line-strong); border-radius: var(--r-md); padding: 0 var(--s-2); min-height: var(--hit); width: 200px; font-size: var(--fs-md); }
.dirty { color: var(--text-3); font-size: var(--fs-sm); }
.issues { flex: 1 1 100%; margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: var(--s-1) var(--s-4); color: var(--warn); font-size: var(--fs-sm); }
.more { color: var(--text-3); }
</style>
