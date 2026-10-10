import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { ModelState } from '../api/types'

const MODEL_POLL_MS = 5000
const ELAPSED_TICK_MS = 1000
const MS_PER_S = 1000
const REASONS: Record<ModelState, string> = {
  ready: '',
  busy: 'The model is busy with another request.',
  down: 'The model backend is not running (start tools/voice_design/live_backend.py when the GPU is free).',
}

export const useModelStore = defineStore('model', () => {
  const state = ref<ModelState>('down')
  const ready = computed(() => state.value === 'ready')
  const reason = computed(() => REASONS[state.value])
  /** Seconds since the model went busy (0 when not busy). Ticks once a second while busy. */
  const busyElapsed = ref(0)
  let busySince: number | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let tick: ReturnType<typeof setInterval> | null = null

  function setState(next: ModelState) {
    state.value = next
    if (next === 'busy' && busySince === null) {
      busySince = Date.now()
      busyElapsed.value = 0
      tick = setInterval(() => (busyElapsed.value = Math.floor((Date.now() - (busySince ?? Date.now())) / MS_PER_S)), ELAPSED_TICK_MS)
    } else if (next !== 'busy') {
      busySince = null
      busyElapsed.value = 0
      if (tick) clearInterval(tick)
      tick = null
    }
  }

  async function refresh() {
    try {
      setState((await api.health()).state)
    } catch {
      setState('down')
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
    if (tick) clearInterval(tick)
    tick = null
  }
  return { state, ready, reason, busyElapsed, refresh, retry: refresh, start, stop }
})
