import { computed, ref } from 'vue'
import type { RegisterAllResult } from '../api/types'
import { useSpeakersStore } from '../stores/speakers'

export type RegisterPhase = 'idle' | 'confirm' | 'busy' | 'done'

/** Register-all flow for the list page: ask (with the consequence), run, then summarise. */
export function useRegisterAll() {
  const store = useSpeakersStore()
  const phase = ref<RegisterPhase>('idle')
  const result = ref<RegisterAllResult | null>(null)
  const error = ref('')

  const picks = computed(() => store.list.filter((s) => s.origin === 'designed' && s.has_pick).length)
  const skipped = computed(() => store.list.length - picks.value)

  function ask() {
    if (phase.value === 'busy' || !picks.value) return
    phase.value = 'confirm'
    result.value = null
    error.value = ''
  }
  function dismiss() {
    if (phase.value !== 'busy') phase.value = 'idle'
  }
  async function run() {
    if (phase.value !== 'confirm') return
    phase.value = 'busy'
    try {
      result.value = await store.registerAll()
      phase.value = 'done'
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      phase.value = 'done'
    }
  }
  return { phase, result, error, picks, skipped, ask, dismiss, run }
}
