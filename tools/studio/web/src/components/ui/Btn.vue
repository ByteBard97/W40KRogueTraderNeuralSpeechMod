<script setup lang="ts">
import Kbd from './Kbd.vue'

export type BtnVariant = 'default' | 'primary' | 'ghost' | 'danger' | 'good'
export type BtnSize = 'sm' | 'md' | 'lg'

withDefaults(
  defineProps<{
    variant?: BtnVariant
    size?: BtnSize
    /** Square icon-only button. Always pass `label`. */
    icon?: boolean
    /** Keycap hint shown after the label. */
    kbd?: string
    /** Accessible name for icon-only buttons. */
    label?: string
    type?: 'button' | 'submit'
    pressed?: boolean
  }>(),
  { variant: 'default', size: 'md', type: 'button', pressed: undefined },
)
</script>

<template>
  <button
    class="btn"
    :class="[`v-${variant}`, `s-${size}`, { icon }]"
    :type="type"
    :aria-label="label"
    :aria-pressed="pressed === undefined ? undefined : pressed"
  >
    <slot />
    <Kbd v-if="kbd" class="hint">{{ kbd }}</Kbd>
  </button>
</template>

<style scoped>
.btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: var(--hit); padding: 0 var(--s-3); border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); font-weight: 500; font-size: var(--fs-md); cursor: pointer; white-space: nowrap; text-decoration: none; }
.btn:hover { background: var(--inset); border-color: var(--n-6); }
.btn:disabled { color: var(--text-off); border-color: var(--line); background: transparent; cursor: not-allowed; opacity: 1; }
.v-primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.v-primary:hover { background: var(--accent-hi); border-color: var(--accent-hi); }
.v-ghost { background: transparent; border-color: transparent; color: var(--text-2); }
.v-ghost:hover { background: var(--hover); color: var(--text); border-color: transparent; }
.v-ghost[aria-pressed="true"] { color: var(--accent-hi); background: var(--accent-tint); }
.v-danger { background: transparent; border-color: var(--bad-line); color: var(--bad); }
.v-danger:hover { background: var(--bad-tint); border-color: var(--bad); }
.v-good { background: transparent; border-color: var(--good-line); color: var(--good); }
.v-good:hover { background: var(--good-tint); border-color: var(--good); }
.v-primary:disabled, .v-danger:disabled, .v-good:disabled { background: transparent; border-color: var(--line); color: var(--text-off); }
.s-lg { min-height: var(--hit-lg); padding: 0 var(--s-4); font-size: 15px; }
.s-sm { min-height: 26px; padding: 0 var(--s-2); font-size: var(--fs-sm); }
.icon { width: var(--hit); padding: 0; }
.icon.s-lg { width: var(--hit-lg); }
.icon.s-sm { width: 26px; }
.btn :slotted(svg) { flex: none; }
.v-primary .hint { background: rgba(0, 0, 0, 0.12); border-color: rgba(0, 0, 0, 0.25); color: var(--accent-ink); }
</style>
