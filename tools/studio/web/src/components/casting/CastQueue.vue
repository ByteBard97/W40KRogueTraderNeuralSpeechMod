<script setup lang="ts">
import type { CastCharacter } from '../../api/types'
import { fileUrl } from '../../utils/fileUrl'
import StatusDot from '../ui/StatusDot.vue'

/** Characters in screen-time order: the ones with the most lines first. */
defineProps<{ rows: CastCharacter[]; selected: string | null }>()
defineEmits<{ select: [speaker: string] }>()
</script>

<template>
  <ul class="queue" aria-label="Characters, most lines first">
    <li v-for="c in rows" :key="c.speaker">
      <button type="button" class="row" :class="{ sel: c.speaker === selected }" :aria-current="c.speaker === selected ? 'true' : undefined" @click="$emit('select', c.speaker)">
        <img v-if="c.portrait" class="thumb" :src="fileUrl(c.portrait)" alt="" loading="lazy" />
        <span v-else class="thumb none" aria-hidden="true">?</span>
        <span class="who"><b>{{ c.display }}</b><span class="meta">{{ c.lines }} lines · {{ c.role ?? c.status }}</span></span>
        <StatusDot :status="c.assignment ? 'good' : 'idle'" :label="c.assignment ? `Cast: ${c.assignment.name}` : 'No voice yet'" />
        <span v-if="c.assignment" class="cast">{{ c.assignment.name }}</span>
      </button>
    </li>
  </ul>
</template>

<style scoped>
.queue { list-style: none; margin: 0; padding: 0; }
.row { display: grid; grid-template-columns: 36px minmax(0, 1fr) 14px; gap: 2px var(--s-3); align-items: center; width: 100%; min-height: 52px; padding: var(--s-2) 10px; border: 0; border-top: 1px solid var(--line); background: transparent; color: inherit; text-align: left; cursor: pointer; font: inherit; }
.row:hover { background: var(--hover); }
.row.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); border-top-color: transparent; }
.thumb { width: 36px; height: 36px; border-radius: var(--r-sm); object-fit: cover; object-position: top; background: var(--inset); grid-row: 1 / 3; }
.thumb.none { display: grid; place-items: center; color: var(--text-3); }
.who { display: flex; flex-direction: column; min-width: 0; }
.who b { color: var(--text); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cast { grid-column: 2 / 4; font-size: var(--fs-xs); color: var(--good); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
