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
  function play(path: string) {
    if (playing.value === path) return stop()
    const a = element()
    a.src = fileUrl(path)
    void a.play().catch(() => (playing.value = null))
    playing.value = path
  }
  return { playing, play, stop }
}
