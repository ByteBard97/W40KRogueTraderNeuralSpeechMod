import { onBeforeUnmount, onMounted, ref } from 'vue'

export const PROBE_POLL_MS = 5000
export type LabState = 'checking' | 'up' | 'down'

/** Is the FX Lab server answering? A no-cors fetch resolves (opaquely) when something listens and rejects when nothing does.
 *  Re-checks every few seconds while it is down, so the panel loads by itself once the server starts. */
export function useLabProbe(url: string) {
  const state = ref<LabState>('checking')
  let timer: ReturnType<typeof setTimeout> | undefined
  let alive = true

  async function check() {
    clearTimeout(timer)
    try {
      await fetch(url, { mode: 'no-cors', cache: 'no-store' })
      state.value = 'up'
    } catch {
      state.value = 'down'
      if (alive) timer = setTimeout(check, PROBE_POLL_MS)
    }
  }
  onMounted(check)
  onBeforeUnmount(() => {
    alive = false
    clearTimeout(timer)
  })
  return { state, retry: () => { state.value = 'checking'; return check() } }
}
