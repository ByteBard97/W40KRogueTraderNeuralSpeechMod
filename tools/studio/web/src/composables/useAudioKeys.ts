import { onBeforeUnmount, onMounted } from 'vue'
import { SEEK_BIG_S, SEEK_SMALL_S, SPEEDS, useGlobalAudio } from './globalAudio'
import { isTypingTarget } from '../utils/keys'

const SPACE = ' '

/** Global audio keys (mounted once by the shell). Space, arrows, `,` `.`, L, `[` `]`. Skipped while typing and for keys a page already handled. */
export function useAudioKeys() {
  const a = useGlobalAudio()

  function onKey(e: KeyboardEvent) {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return
    const step = e.shiftKey ? SEEK_BIG_S : SEEK_SMALL_S
    switch (e.key) {
      case SPACE:
        if (isActivatable(e.target) || !a.hasClip.value) return
        a.toggle()
        break
      case 'ArrowLeft':
        if (!a.hasClip.value || isSliderTarget(e.target)) return
        a.seekBy(-step)
        break
      case 'ArrowRight':
        if (!a.hasClip.value || isSliderTarget(e.target)) return
        a.seekBy(step)
        break
      case ',':
        a.state.transport.prev?.()
        break
      case '.':
        a.state.transport.next?.()
        break
      case 'l':
      case 'L':
        a.setLoop(!a.state.loop)
        break
      case '[':
        a.setRate(SPEEDS[Math.max(SPEEDS.indexOf(a.state.rate as (typeof SPEEDS)[number]) - 1, 0)])
        break
      case ']':
        a.setRate(SPEEDS[Math.min(SPEEDS.indexOf(a.state.rate as (typeof SPEEDS)[number]) + 1, SPEEDS.length - 1)])
        break
      default:
        return
    }
    e.preventDefault()
  }
  onMounted(() => window.addEventListener('keydown', onKey))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
}

/** A focused button, link or summary keeps Space for itself, so keyboard users can still press it. */
function isActivatable(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  return !!el && !!el.closest?.('button, a[href], summary, [role="button"], [role="tab"], [role="switch"], input')
}
function isSliderTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  return !!el && el.getAttribute?.('role') === 'slider'
}
