import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'

const QA_EXPORT_RUN = 'export'

/** The numbers shown beside the top-bar links. Each is null until it loads, and stays null when its endpoint fails. */
export const useNavCountsStore = defineStore('navCounts', () => {
  const speakersLeft = ref<number | null>(null)
  const pools = ref<number | null>(null)
  const matchesUndecided = ref<number | null>(null)
  const qaClips = ref<number | null>(null)

  const attempt = async (job: () => Promise<void>) => {
    try {
      await job()
    } catch {
      /* a missing count must never break the shell */
    }
  }

  async function load() {
    await Promise.all([
      attempt(async () => { speakersLeft.value = (await api.speakers()).filter((s) => s.status === 'needs_voice').length }),
      attempt(async () => { pools.value = (await api.pools()).slots.length }),
      attempt(async () => { matchesUndecided.value = (await api.matches({ limit: 1 })).counts.undecided }),
      attempt(async () => {
        const runs = await api.qaRuns()
        qaClips.value = (runs.find((r) => r.id === QA_EXPORT_RUN) ?? runs[0])?.clips ?? null
      }),
    ])
  }
  return { speakersLeft, pools, matchesUndecided, qaClips, load }
})
