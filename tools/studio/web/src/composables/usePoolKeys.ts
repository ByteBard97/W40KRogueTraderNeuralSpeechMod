import { onBeforeUnmount, onMounted, type Ref } from 'vue'
import { usePoolsStore } from '../stores/pools'
import { isTypingTarget } from '../utils/keys'

export type PoolZone = 'review' | 'spot'
export interface SpotKeys {
  mark: (v: 'right' | 'wrong') => void
  step: (delta: number) => void
}

/**
 * Page keys for Pools. The review queue and the spot-check panel share J and K, so the last place
 * the user clicked or focused (`zone`) decides which one a key drives.
 */
export function usePoolKeys(zone: Ref<PoolZone>, spot: () => SpotKeys | null, focusMove: () => void) {
  const pools = usePoolsStore()

  function review(key: string) {
    const e = pools.current
    if (key === 'j') pools.moveCursor(1)
    else if (key === 'k') pools.moveCursor(-1)
    else if (!e) return false
    else if (key === 'a') void pools.accept(e)
    else if (key === 's') pools.skip(e)
    else if (key === 'm') {
      if (pools.guessIsChosen(e)) focusMove()
      else void pools.moveChosen(e)
    } else return false
    return true
  }
  function spotCheck(key: string) {
    const s = spot()
    if (!s) return false
    if (key === 'y') s.mark('right')
    else if (key === 'w') s.mark('wrong')
    else if (key === 'j') s.step(1)
    else if (key === 'k') s.step(-1)
    else return false
    return true
  }
  function onKey(ev: KeyboardEvent) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.defaultPrevented || isTypingTarget(ev.target)) return
    const key = ev.key.toLowerCase()
    const handled = zone.value === 'spot' && spot() ? spotCheck(key) : review(key)
    if (handled) ev.preventDefault()
  }
  onMounted(() => document.addEventListener('keydown', onKey))
  onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
}
