<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LabelDef } from '../../api/types'
import type { LabelFilters } from '../../utils/castVoices'

/** Filter chips for the label set: pick values per label, labels combine with "and". Required labels first, the rest under "More". */
const props = defineProps<{ schema: LabelDef[]; modelValue: LabelFilters }>()
const emit = defineEmits<{ 'update:modelValue': [value: LabelFilters] }>()

const more = ref(false)
const filterable = computed(() => props.schema.filter((d) => d.kind !== 'text'))
const shown = computed(() => filterable.value.filter((d) => d.required || more.value))
const extras = computed(() => filterable.value.filter((d) => !d.required).length)
const active = computed(() => Object.values(props.modelValue).reduce((n, v) => n + v.length, 0))

function toggle(key: string, option: string) {
  const cur = props.modelValue[key] ?? []
  const next = cur.includes(option) ? cur.filter((x) => x !== option) : [...cur, option]
  emit('update:modelValue', { ...props.modelValue, [key]: next })
}
const on = (key: string, option: string) => (props.modelValue[key] ?? []).includes(option)
</script>

<template>
  <div class="lf">
    <div v-for="d in shown" :key="d.key" class="group" role="group" :aria-label="`Filter by ${d.label}`">
      <span class="name">{{ d.label }}</span>
      <button v-for="o in d.options" :key="o" type="button" class="chip" :aria-pressed="on(d.key, o)" @click="toggle(d.key, o)">{{ o }}</button>
    </div>
    <div class="tail">
      <button v-if="extras" type="button" class="link" @click="more = !more">{{ more ? 'Fewer filters' : `More filters (${extras})` }}</button>
      <button v-if="active" type="button" class="link" @click="emit('update:modelValue', {})">Clear filters ({{ active }})</button>
    </div>
  </div>
</template>

<style scoped>
.lf { display: flex; flex-direction: column; gap: var(--s-2); }
.group { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.name { width: 78px; flex: none; color: var(--text-3); font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.05em; }
.chip { min-height: 24px; padding: 0 9px; border-radius: 12px; border: 1px solid var(--line-strong); background: var(--n-1); color: var(--text-2); font-size: var(--fs-sm); cursor: pointer; }
.chip:hover { background: var(--hover); }
.chip[aria-pressed="true"] { background: var(--accent-tint); border-color: var(--accent); color: var(--accent-hi); font-weight: 600; }
.tail { display: flex; gap: var(--s-3); }
.link { background: none; border: 0; padding: 0; color: var(--text-3); font-size: var(--fs-xs); cursor: pointer; text-decoration: underline; }
.link:hover { color: var(--text); }
</style>
