import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { ModelState } from '../api/types'

const MODEL_POLL_MS = 5000
const REASONS: Record<ModelState, string> = {
  ready: '',
  busy: 'The model is busy with another request.',
  down: 'The model backend is not running (start tools/voice_design/live_backend.py when the GPU is free).',
}

export const useModelStore = defineStore('model', () => {
  const state = ref<ModelState>('down')
  const ready = computed(() => state.value === 'ready')
  const reason = computed(() => REASONS[state.value])
  let timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    try {
      state.value = (await api.health()).state
    } catch {
      state.value = 'down'
    }
  }
  function start() {
    if (timer) return
    refresh()
    timer = setInterval(refresh, MODEL_POLL_MS)
  }
  function stop() {
    if (timer) clearInterval(timer)
    timer = null
  }
  return { state, ready, reason, refresh, start, stop }
})
