import { computed, onBeforeUnmount, onMounted } from 'vue'
import type { MatchValue } from '../api/types'
import { useMatchesStore } from '../stores/matches'
import { entryName } from '../utils/matchText'
import { isTypingTarget } from '../utils/keys'
import { useGlobalAudio, type Transport } from './globalAudio'
import { useShortcuts } from './useShortcuts'
import { useToasts } from './useToasts'

const SPACE = ' '

/** Keys, auto-advance, undo toast and audition for the review queue. The view stays thin. */
export function useMatchReview() {
  const store = useMatchesStore()
  const audio = useGlobalAudio()
  const toasts = useToasts()

  useShortcuts({
    title: 'Matches',
    groups: [
      { title: 'Review', items: [
        { label: 'Accept the proposed speaker', keys: ['A'] },
        { label: 'Reject the match', keys: ['R'] },
        { label: 'Undo the last decision', keys: ['Z'] },
      ] },
      { title: 'Move', items: [
        { label: 'Next / previous match', keys: ['J', 'K'] },
        { label: 'Next unreviewed', keys: ['N'] },
        { label: 'Hear the proposed speaker', keys: ['Space'] },
        { label: 'Search', keys: ['/'] },
      ] },
    ],
  })

  const sample = computed(() => (store.current?.has_bank ? (store.current.speaker_sample ?? null) : null))
  const hearing = computed(() => !!sample.value && audio.playing.value === sample.value)

  function hear() {
    const row = store.current
    if (!row || !sample.value) return
    audio.play(sample.value, undefined, { title: `${row.speaker} bank sample`, subtitle: `proposed speaker for ${entryName(row)}` })
  }

  async function decide(value: Exclude<MatchValue, ''>) {
    const row = store.current
    if (!row) return
    const { id, decision: before } = row
    const label = `${value === 'accept' ? 'Accepted' : 'Rejected'} ${entryName(row)} → ${row.speaker} · ${row.conversation}`
    const saved = store.decide(id, value)
    toasts.undo(label, () => { store.select(id); void store.decide(id, before) })
    await store.nextUnreviewed()
    await saved
  }

  const next = () => void store.move(1)
  const prev = () => void store.move(-1)

  function onKey(e: KeyboardEvent) {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return
    const onButton = (e.target as HTMLElement | null)?.closest?.('button, a, summary')
    const k = e.key.toLowerCase()
    if (e.key === SPACE) {
      // Space on a focused button presses it; with the sample already loaded the shell's own Space toggles it.
      if (onButton || !sample.value || audio.state.id === sample.value) return
      hear()
    } else if (k === 'a') void decide('accept')
    else if (k === 'r') void decide('reject')
    else if (k === 'j') next()
    else if (k === 'k') prev()
    else if (k === 'n') void store.nextUnreviewed()
    else return
    e.preventDefault()
  }

  const transport: Transport = { prev, next }
  onMounted(() => {
    document.addEventListener('keydown', onKey)
    audio.setTransport(transport)
  })
  onBeforeUnmount(() => {
    document.removeEventListener('keydown', onKey)
    audio.clearTransport(transport)
    void store.flushPools()
  })

  return { hear, hearing, decide, next, prev }
}
