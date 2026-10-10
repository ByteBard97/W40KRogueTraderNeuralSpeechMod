<script setup lang="ts">
import type { SpeakerRow } from '../../utils/speakerRows'
import DataRow from '../ui/DataRow.vue'
import Icon from '../ui/Icon.vue'
import StatusDot from '../ui/StatusDot.vue'
import Tag from '../ui/Tag.vue'

const props = defineProps<{ row: SpeakerRow; current: boolean }>()
const TAG_LABEL = { named: 'designed', slot: 'slot', real: 'real' } as const
const TAG_VARIANT = { named: 'designed', slot: 'slot', real: 'real' } as const
const dotLabel = (r: SpeakerRow) => ({ registered: 'registered', picked: 'picked', progress: 'ranking in progress', idle: 'not started' })[r.stage]
</script>

<template>
  <RouterLink v-slot="{ href, navigate }" custom :to="`/speakers/${props.row.speaker.slug}`">
    <DataRow as="a" class="spk" :href="href" :selected="current" :data-slug="row.speaker.slug" :data-stage="row.stage" @click="navigate">
      <template #lead><StatusDot :status="row.dot" :label="dotLabel(row)" /></template>
      <span class="nm" :class="{ mono: row.kind === 'slot' }">{{ row.speaker.name }}</span>
      <template #meta>
        <span class="meta">
          <span class="tagc"><Tag :variant="TAG_VARIANT[row.kind]">{{ TAG_LABEL[row.kind] }}</Tag></span>
          <span class="num lines" :class="{ zero: row.lines === 0 }">{{ row.lines.toLocaleString('en-US') }}</span>
          <span class="st" :class="{ on: row.active }">{{ row.text }}</span>
        </span>
      </template>
      <template #end><Icon name="chev" :size="14" class="chev" /></template>
    </DataRow>
  </RouterLink>
</template>

<style scoped>
.spk { flex-wrap: nowrap; }
.spk :deep(.main) { flex: 1 1 0; }
.nm { display: block; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nm.mono { font-weight: 400; font-size: 13px; }
.meta { --tag-col: 76px; --lines-col: 64px; --status-col: 120px; display: grid; grid-template-columns: var(--tag-col) var(--lines-col) var(--status-col); align-items: center; gap: var(--s-3); }
.tagc { justify-self: end; }
.lines { text-align: right; color: var(--text-2); }
.lines.zero { color: var(--text-3); }
.st { font-size: var(--fs-sm); color: var(--text-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.st.on { color: var(--accent-hi); }
.chev { color: var(--text-3); }
@media (max-width: 640px) {
  .meta { grid-template-columns: var(--lines-col); }
  .tagc, .st { display: none; }
}
</style>
