<script setup lang="ts">
import { useLabStore } from '../../stores/lab'
import { recipeSummary } from '../../utils/labRecipe'
import SectionCard from '../shared/SectionCard.vue'
import RecipeBar from './RecipeBar.vue'
import RecipeModel from './RecipeModel.vue'
import RecipePronunciation from './RecipePronunciation.vue'
import RecipePunctuation from './RecipePunctuation.vue'
import RecipeSplit from './RecipeSplit.vue'

defineProps<{ seedCount: number }>()
const emit = defineEmits<{ 'update:seedCount': [n: number] }>()
const lab = useLabStore()
</script>

<template>
  <section class="recipe" aria-label="Recipe">
    <h2 class="list-head">Recipe</h2>
    <template v-if="lab.recipe">
      <RecipeBar />
      <p class="muted summary" data-summary>{{ recipeSummary(lab.recipe) }}</p>
      <SectionCard title="Model"><RecipeModel :seed-count="seedCount" @update:seed-count="emit('update:seedCount', $event)" /></SectionCard>
      <SectionCard title="Pronunciation" :summary="`${lab.recipe.pronunciation.length} overrides`" collapsed-by-default><RecipePronunciation /></SectionCard>
      <SectionCard title="Punctuation" collapsed-by-default><RecipePunctuation /></SectionCard>
      <SectionCard title="Splitting" :summary="lab.recipe.split.mode" collapsed-by-default><RecipeSplit /></SectionCard>
    </template>
    <p v-else class="muted">Loading the recipe…</p>
  </section>
</template>

<style scoped>
.recipe { display: flex; flex-direction: column; gap: var(--s-2); min-width: 0; }
.summary { margin: 0 0 var(--s-1); font-family: var(--font-mono); font-size: var(--fs-sm); }
.recipe :deep(.section) { margin-bottom: 0; }
</style>
