import { ref } from 'vue'
import { fileUrl } from '../utils/fileUrl'

const playing = ref<string | null>(null)
let el: HTMLAudioElement | null = null

function element(): HTMLAudioElement {
  if (!el) {
    el = new Audio()
    el.addEventListener('ended', () => (playing.value = null))
  }
  return el
}

export function useAudioPlayer() {
  function stop() {
    if (el) el.pause()
    playing.value = null
  }
  /** `id` names what is playing; `url` overrides where the audio comes from (default: /file for a repo path). */
  function play(id: string, url?: string) {
    if (playing.value === id) return stop()
    const a = element()
    a.src = url ?? fileUrl(id)
    void a.play().catch(() => (playing.value = null))
    playing.value = id
  }
  return { playing, play, stop }
}
