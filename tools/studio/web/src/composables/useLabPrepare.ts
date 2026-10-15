import { onBeforeUnmount, watch } from 'vue'
import { useLabStore } from '../stores/lab'

export const PREPARE_DEBOUNCE_MS = 300

/** Re-run the text stages ~300 ms after the recipe stops changing. Selecting a line prepares at once (the store does that). */
export function useLabPrepare(debounceMs = PREPARE_DEBOUNCE_MS) {
  const lab = useLabStore()
  let timer: ReturnType<typeof setTimeout> | null = null
  const stopWatch = watch(() => lab.recipe, () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => void lab.prepare(), debounceMs)
  }, { deep: true })
  onBeforeUnmount(() => {
    stopWatch()
    if (timer) clearTimeout(timer)
  })
}
