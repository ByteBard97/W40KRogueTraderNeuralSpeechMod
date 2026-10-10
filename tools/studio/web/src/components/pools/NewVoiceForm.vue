<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NewSlotBody } from '../../api/types'
import Btn from '../ui/Btn.vue'
import Seg from '../ui/Seg.vue'

type Gender = NewSlotBody['gender']
const GENDERS: { value: Gender; label: string }[] = [
  { value: 'male', label: 'Male' },
  { value: 'female', label: 'Female' },
  { value: 'any', label: 'Any' },
]
const DEFAULT_SPECIES = 'human'

/** Makes a shared voice slot by hand. It then shows up under Speakers as a designed speaker with no source yet. */
const props = defineProps<{ name?: string; gender?: string; species?: string; confirmLabel?: string }>()
const emit = defineEmits<{ create: [body: NewSlotBody]; cancel: [] }>()

const name = ref(props.name ?? '')
const gender = ref<Gender>(props.gender === 'male' || props.gender === 'female' ? props.gender : 'any')
const species = ref(props.species && props.species !== 'unknown' ? props.species : DEFAULT_SPECIES)
const age = ref('')
const description = ref('')
const ready = computed(() => name.value.trim().length > 0)

function submit() {
  if (!ready.value) return
  emit('create', { name: name.value.trim(), gender: gender.value, species: species.value.trim() || DEFAULT_SPECIES, ...(age.value.trim() ? { age: age.value.trim() } : {}), ...(description.value.trim() ? { description: description.value.trim() } : {}) })
}
</script>

<template>
  <form class="nv" aria-label="New designed voice" @submit.prevent="submit" @keydown.esc.stop="emit('cancel')">
    <label class="field name"><span class="lbl">Name</span><input v-model="name" data-nv-name placeholder="e.g. Dock foreman" autocomplete="off" /></label>
    <Seg v-model="gender" :options="GENDERS" aria-label="Gender" />
    <label class="field"><span class="lbl">Species</span><input v-model="species" data-nv-species autocomplete="off" /></label>
    <label class="field"><span class="lbl">Age</span><input v-model="age" data-nv-age placeholder="optional" autocomplete="off" /></label>
    <label class="field desc"><span class="lbl">Voice</span><input v-model="description" data-nv-description placeholder="optional, e.g. female cyborg, modulated vox voice" autocomplete="off" /></label>
    <span class="acts">
      <Btn type="submit" variant="primary" size="sm" :disabled="!ready" data-nv-create>{{ confirmLabel ?? 'Create voice' }}</Btn>
      <Btn variant="ghost" size="sm" kbd="Esc" @click="emit('cancel')">Cancel</Btn>
    </span>
    <span class="note">Creates a designed speaker with no source clip. Design it under Speakers.</span>
  </form>
</template>

<style scoped>
.nv { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); padding: var(--s-3); border-radius: var(--r-md); background: var(--inset); border: 1px solid var(--line-strong); }
.name { flex: 1 1 200px; }
.field { min-height: 28px; }
.desc { flex: 1 1 100%; }
.acts { display: flex; gap: var(--s-2); margin-left: auto; }
.note { flex-basis: 100%; font-size: var(--fs-sm); color: var(--text-3); }
</style>
