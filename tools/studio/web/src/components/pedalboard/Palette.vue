<script setup lang="ts">
import { computed, ref } from 'vue'
import { INPUT_TYPE, OUTPUT_TYPE } from '../../pedalboard/graph'
import type { CatalogBlock } from '../../pedalboard/types'
import { PALETTE_MIME } from './paletteDrag'

const CATEGORY_ORDER = ['Tone', 'Pitch & voice', 'Metal', 'Modulation', 'Space', 'Stereo', 'Routing', 'Output']

const props = defineProps<{ blocks: CatalogBlock[] }>()
const emit = defineEmits<{ add: [blockId: string] }>()

const closed = ref(new Set<string>())

// Input and Output already sit on the board and can't be added again.
const groups = computed(() => {
  const usable = props.blocks.filter((b) => b.id !== INPUT_TYPE && b.id !== OUTPUT_TYPE)
  const names = [...CATEGORY_ORDER, ...usable.map((b) => b.category).filter((c) => !CATEGORY_ORDER.includes(c))]
  return [...new Set(names)]
    .map((name) => ({ name, blocks: usable.filter((b) => b.category === name) }))
    .filter((g) => g.blocks.length)
})

function toggle(name: string) {
  const next = new Set(closed.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  closed.value = next
}

function dragStart(e: DragEvent, id: string) {
  e.dataTransfer?.setData(PALETTE_MIME, id)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'
}
</script>

<template>
  <aside class="palette" aria-label="Pedals" data-testid="palette">
    <section v-for="g in groups" :key="g.name" class="group" :data-testid="`palette-group-${g.name}`">
      <button type="button" class="group-head" :aria-expanded="!closed.has(g.name)" @click="toggle(g.name)">
        <span class="chev" aria-hidden="true">{{ closed.has(g.name) ? '+' : '-' }}</span>{{ g.name }}
        <span class="n">{{ g.blocks.length }}</span>
      </button>
      <ul v-show="!closed.has(g.name)" class="items">
        <li
          v-for="b in g.blocks"
          :key="b.id"
          class="item"
          tabindex="0"
          draggable="true"
          :title="b.description"
          :data-testid="`palette-${b.id}`"
          @dragstart="dragStart($event, b.id)"
          @dblclick="emit('add', b.id)"
          @keydown.enter.prevent="emit('add', b.id)"
        >
          <span class="name">{{ b.name }}</span>
          <span class="desc">{{ b.description }}</span>
        </li>
      </ul>
    </section>
  </aside>
</template>

<style scoped>
.palette { display: flex; flex-direction: column; gap: var(--s-2); overflow-y: auto; padding: var(--s-2); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); }
.group-head { display: flex; align-items: center; gap: var(--s-2); width: 100%; background: transparent; border: 0; color: var(--text-2); font-weight: 600; font-size: var(--fs-sm); text-transform: uppercase; letter-spacing: 0.05em; padding: var(--s-1); cursor: pointer; text-align: left; }
.group-head:hover { color: var(--text); }
.chev { width: 10px; font-family: var(--font-mono); color: var(--text-3); }
.n { margin-left: auto; font-family: var(--font-mono); font-weight: 400; color: var(--text-3); }
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
.item { display: flex; flex-direction: column; gap: 2px; padding: var(--s-1) var(--s-2); border-radius: var(--r-sm); cursor: grab; border: 1px solid transparent; }
.item:hover, .item:focus-visible { background: var(--hover); border-color: var(--line-strong); outline: none; }
.name { color: var(--text); font-size: var(--fs-md); }
.desc { display: none; color: var(--text-3); font-size: var(--fs-xs); line-height: var(--lh-tight); }
.item:hover .desc, .item:focus-visible .desc { display: block; }
</style>
