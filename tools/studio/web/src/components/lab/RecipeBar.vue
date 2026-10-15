<script setup lang="ts">
import { computed, ref } from 'vue'
import { useLabStore } from '../../stores/lab'
import Btn from '../ui/Btn.vue'
import SelectField from '../ui/SelectField.vue'

const lab = useLabStore()
const name = ref('')
const options = computed(() => lab.recipes.map((r, i) => ({ value: String(i), label: i === 0 ? `${r.name} (baseline)` : r.name })))
const current = computed(() => String(lab.recipes.findIndex((r) => r.name === lab.recipe?.name)))
const pick = (i: string) => lab.recipes[Number(i)] && lab.loadRecipe(lab.recipes[Number(i)])
async function save() {
  await lab.saveRecipe(name.value)
  name.value = ''
}
</script>

<template>
  <div class="bar">
    <SelectField label="Recipe" :options="options" :model-value="current" @update:model-value="pick" />
    <Btn size="sm" data-reset @click="lab.resetRecipe()">Reset to production</Btn>
    <label class="field"><span class="lbl">Save as</span><input v-model="name" placeholder="recipe name" @keydown.enter="save" /></label>
    <Btn size="sm" variant="primary" data-save :disabled="!name.trim()" @click="save">Save</Btn>
  </div>
</template>

<style scoped>
.bar { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
</style>
