<script setup lang="ts">
import type { CastCharacter } from '../../api/types'
import { fileUrl } from '../../utils/fileUrl'
import Btn from '../ui/Btn.vue'
import Tag from '../ui/Tag.vue'

/** One character: portrait, what we know about them, a few of their lines, and who they are cast as. */
const props = defineProps<{ character: CastCharacter; portraits: string[] }>()
const emit = defineEmits<{ clear: []; portrait: [name: string | null] }>()
const onPick = (e: Event) => emit('portrait', (e.target as HTMLSelectElement).value || null)
</script>

<template>
  <section class="panel">
    <div class="pic">
      <img v-if="character.portrait" :src="fileUrl(character.portrait)" :alt="`Portrait of ${character.display}`" />
      <div v-else class="nopic">No portrait found</div>
      <label class="pick">Portrait
        <select :value="character.portrait_name ?? ''" aria-label="Portrait" @change="onPick">
          <option value="">(none)</option>
          <option v-for="n in portraits" :key="n" :value="n">{{ n }}</option>
        </select>
      </label>
    </div>
    <div class="info">
      <h2 class="name">{{ character.display }}</h2>
      <div class="tags">
        <Tag v-if="character.rank">#{{ character.rank }} by lines</Tag>
        <Tag v-else variant="slot">nameless group</Tag>
        <Tag>{{ character.lines }} lines</Tag>
        <Tag>~{{ character.approx_minutes }} min</Tag>
        <Tag v-if="character.gender">{{ character.gender }}</Tag>
        <Tag v-if="character.species">{{ character.species }}</Tag>
        <Tag v-if="character.age">{{ character.age }}</Tag>
        <Tag v-if="character.status === 'designed'" variant="designed">designed voice today</Tag>
      </div>
      <p v-if="character.role" class="role">{{ character.role }}</p>
      <p v-if="character.voice_description" class="desc">{{ character.voice_description }}</p>
      <ul v-if="character.samples.length" class="samples" aria-label="Sample lines">
        <li v-for="(t, i) in character.samples" :key="i">{{ t }}</li>
      </ul>
      <p v-if="character.assignment" class="cast">Cast as <b>{{ character.assignment.name }}</b>
        <Btn size="sm" variant="ghost" @click="emit('clear')">Clear</Btn>
      </p>
    </div>
  </section>
</template>

<style scoped>
.panel { display: flex; flex-wrap: wrap; gap: var(--s-4); padding: var(--s-4); background: var(--raised); border: 1px solid var(--line); border-radius: var(--r-lg); }
.pic { flex: 0 0 150px; display: flex; flex-direction: column; gap: var(--s-2); }
.pic img { width: 150px; height: 200px; object-fit: cover; object-position: top; border-radius: var(--r-md); background: var(--inset); }
.nopic { width: 150px; height: 200px; display: grid; place-items: center; color: var(--text-3); background: var(--inset); border-radius: var(--r-md); font-size: var(--fs-sm); text-align: center; }
.pick { display: flex; flex-direction: column; gap: 2px; font-size: var(--fs-xs); color: var(--text-3); }
.pick select { background: var(--inset); color: var(--text); border: 1px solid var(--line-strong); border-radius: var(--r-sm); min-height: 28px; }
.info { flex: 1 1 280px; min-width: 0; display: flex; flex-direction: column; gap: var(--s-2); }
.name { margin: 0; font-family: var(--font-display); font-size: var(--fs-xl); letter-spacing: 0.03em; }
.tags { display: flex; flex-wrap: wrap; gap: var(--s-1); }
.role { margin: 0; color: var(--text-2); }
.desc { margin: 0; color: var(--text-2); font-style: italic; }
.samples { margin: 0; padding-left: var(--s-4); color: var(--text-2); font-size: var(--fs-sm); display: flex; flex-direction: column; gap: var(--s-1); }
.cast { margin: 0; color: var(--good); display: flex; align-items: center; gap: var(--s-2); }
</style>
