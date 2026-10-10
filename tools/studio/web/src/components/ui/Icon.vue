<script setup lang="ts">
/** 16x16 icon set taken from the design system sheet. Decorative: pair with text or an aria-label on the control. */
import { computed } from 'vue'

export type IconName =
  | 'check' | 'x' | 'warn' | 'chev' | 'play' | 'pause' | 'prev' | 'next' | 'search' | 'loop' | 'volume' | 'up' | 'star' | 'brand'

interface IconDef { d: string; fill?: boolean; stroke?: number }
const ICONS: Record<IconName, IconDef> = {
  check: { d: 'M3 8.5l3 3 7-7', stroke: 2 },
  x: { d: 'M4 4l8 8M12 4l-8 8', stroke: 2 },
  warn: { d: 'M8 2l6.5 11.5h-13zM8 6.5v3M8 11.5v.2', stroke: 1.8 },
  chev: { d: 'M6 3l5 5-5 5', stroke: 1.8 },
  play: { d: 'M4 2.5v11l9-5.5z', fill: true },
  pause: { d: 'M4 2.5h3v11H4zM9 2.5h3v11H9z', fill: true },
  prev: { d: 'M4 3v10M13 3L6 8l7 5z', fill: true, stroke: 1.4 },
  next: { d: 'M12 3v10M3 3l7 5-7 5z', fill: true, stroke: 1.4 },
  search: { d: 'M10.5 10.5L14 14M11.5 7a4.5 4.5 0 1 1-9 0a4.5 4.5 0 0 1 9 0z', stroke: 1.6 },
  loop: { d: 'M3 7a4 4 0 0 1 4-4h5M10 1l2 2-2 2M13 9a4 4 0 0 1-4 4H4M6 15l-2-2 2-2', stroke: 1.5 },
  volume: { d: 'M2 6h3l4-3v10l-4-3H2zM11.5 5.5a3.5 3.5 0 0 1 0 5', stroke: 1.5 },
  up: { d: 'M8 13V3M4 7l4-4 4 4', stroke: 1.8 },
  star: { d: 'M8 1.5l2 4.2 4.5.6-3.3 3.1.8 4.5L8 11.7l-4 2.2.8-4.5L1.5 6.3 6 5.7z', fill: true },
  brand: { d: 'M2 19V8a7 7 0 0 1 14 0v11M6 15v-4M9 16V8M12 15v-4', stroke: 1.6 },
}
const props = withDefaults(defineProps<{ name: IconName; size?: number }>(), { size: 16 })
const def = computed(() => ICONS[props.name])
const viewBox = computed(() => (props.name === 'brand' ? '0 0 18 20' : '0 0 16 16'))
</script>

<template>
  <svg :width="size" :height="props.name === 'brand' ? size * (20 / 18) : size" :viewBox="viewBox" aria-hidden="true" focusable="false">
    <path
      :d="def.d"
      :fill="def.fill ? 'currentColor' : 'none'"
      :stroke="def.stroke ? 'currentColor' : 'none'"
      :stroke-width="def.stroke"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>
