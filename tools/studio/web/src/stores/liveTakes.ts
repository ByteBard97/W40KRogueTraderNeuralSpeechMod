import { defineStore } from 'pinia'
import { ref, toRaw } from 'vue'
import type { LiveTake } from '../api/types'

/** Unkept design takes, per speaker slug, so they survive moving to another speaker and back within the session. */
export const useLiveTakesStore = defineStore('liveTakes', () => {
  const bySlug = ref<Record<string, LiveTake[]>>({})

  const forSlug = (slug: string): LiveTake[] => bySlug.value[slug] ?? []

  function add(slug: string, take: LiveTake): LiveTake {
    bySlug.value[slug] = [take, ...forSlug(slug)]
    return take
  }

  function remove(slug: string, take: LiveTake) {
    bySlug.value[slug] = forSlug(slug).filter((t) => toRaw(t) !== toRaw(take))
  }
  return { forSlug, add, remove }
})
