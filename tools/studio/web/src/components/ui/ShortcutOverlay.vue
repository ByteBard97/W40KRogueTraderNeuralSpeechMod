<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { GLOBAL_SHORTCUTS, useShortcutOverlay } from '../../composables/useShortcuts'
import { isTypingTarget } from '../../utils/keys'
import Btn from './Btn.vue'
import Kbd from './Kbd.vue'

/** Global overlay (mounted once by the shell). Shows the registered page shortcuts plus the global ones. Opens on "?". */
const { page, open, hide, toggle } = useShortcutOverlay()
const dialog = ref<HTMLElement | null>(null)
let opener: HTMLElement | null = null

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) {
    e.preventDefault()
    return hide()
  }
  if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey && !isTypingTarget(e.target)) {
    e.preventDefault()
    toggle()
  }
}
watch(open, async (on) => {
  if (on) {
    opener = document.activeElement as HTMLElement | null
    await nextTick()
    dialog.value?.focus()
  } else opener?.focus?.()
})
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div v-if="open" class="scrim" @click.self="hide">
    <div ref="dialog" class="overlay" role="dialog" aria-modal="true" :aria-label="`Keyboard shortcuts${page ? ` for ${page.title}` : ''}`" tabindex="-1">
      <div class="head">
        <b class="ttl">Shortcuts{{ page ? ` · ${page.title}` : '' }}</b>
        <span class="muted note">Press <Kbd>?</Kbd> any time · <Kbd>Esc</Kbd> closes</span>
        <Btn size="sm" variant="ghost" @click="hide">Close</Btn>
      </div>
      <div class="keys">
        <div v-for="g in [...(page?.groups ?? []), GLOBAL_SHORTCUTS]" :key="g.title">
          <h4>{{ g.title }}</h4>
          <div v-for="it in g.items" :key="it.label" class="k">
            {{ it.label }}<span class="caps"><Kbd v-for="k in it.keys" :key="k">{{ k }}</Kbd></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; z-index: var(--z-overlay); background: var(--scrim); display: flex; align-items: center; justify-content: center; padding: var(--s-4); overflow-y: auto; }
.overlay { background: var(--n-2); border: 1px solid var(--line-strong); border-radius: var(--r-lg); box-shadow: var(--e-3); padding: var(--s-5); display: flex; flex-direction: column; gap: var(--s-4); max-width: 720px; width: 100%; max-height: 100%; overflow-y: auto; }
.overlay:focus { outline: none; }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-4); justify-content: space-between; }
.ttl { font-size: 16px; }
.note { font-size: var(--fs-sm); margin-left: auto; }
.keys { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: var(--s-2) var(--s-5); }
h4 { margin: 0 0 4px; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); }
.k { display: flex; justify-content: space-between; align-items: center; gap: var(--s-3); padding: 4px 0; font-size: 13px; border-bottom: 1px solid var(--line); }
.caps { display: inline-flex; gap: 4px; }
</style>
