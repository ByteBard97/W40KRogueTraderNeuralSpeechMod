import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useSpeakersStore } from '../stores/speakers'
import { isTypingTarget } from '../utils/keys'
import { continueTarget, countRows, matchesFilter, toRow, type ShowFilter, type SpeakerRow } from '../utils/speakerRows'
import { useGlobalAudio } from './globalAudio'

const KEY_DOWN = 'j'
const KEY_UP = 'k'
const KEY_NEXT = 'n'

/** State and keys of the Speakers list: filter, groups, a row cursor (J K), Enter opens, N continues, Space plays the row. `locked` mutes the keys (a confirm is open). */
export function useSpeakerList(locked: Ref<boolean>) {
  const store = useSpeakersStore()
  const router = useRouter()
  const audio = useGlobalAudio()
  const q = ref('')
  const show = ref<ShowFilter>('all')
  const cursor = ref<string | null>(null)

  const all = computed(() => store.list.map((s) => toRow(s, store.slotLines)))
  const counts = computed(() => countRows(all.value))
  const next = computed(() => continueTarget(all.value))
  const shown = computed(() => all.value.filter((r) => matchesFilter(r, q.value, show.value)))

  const inStatus = (status: string, rows: SpeakerRow[]) => rows.filter((r) => r.speaker.status === status)
  const needs = computed(() => inStatus('needs_voice', shown.value))
  const groups = computed(() => ({
    named: needs.value.filter((r) => r.kind !== 'slot'),
    slots: needs.value.filter((r) => r.kind === 'slot'),
    source: inStatus('source', shown.value),
    profile: inStatus('profile', shown.value),
  }))
  const totals = computed(() => ({
    needs: inStatus('needs_voice', all.value).length,
    source: inStatus('source', all.value).length,
    profile: inStatus('profile', all.value).length,
  }))
  const slotLineTotal = computed(() => groups.value.slots.reduce((n, r) => n + r.lines, 0))
  /** Visual order, so J and K walk the list top to bottom. */
  const order = computed(() => [...groups.value.named, ...groups.value.slots, ...groups.value.source, ...groups.value.profile])

  watch(order, (o) => {
    if (cursor.value && !o.some((r) => r.speaker.slug === cursor.value)) cursor.value = null
  })

  const cursorRow = computed(() => order.value.find((r) => r.speaker.slug === cursor.value) ?? null)

  function move(delta: number) {
    const o = order.value
    if (!o.length) return
    const i = o.findIndex((r) => r.speaker.slug === cursor.value)
    const j = i < 0 ? (delta > 0 ? 0 : o.length - 1) : Math.min(o.length - 1, Math.max(0, i + delta))
    cursor.value = o[j].speaker.slug
    document.querySelector(`[data-slug="${CSS.escape(cursor.value)}"]`)?.scrollIntoView({ block: 'nearest' })
  }
  const open = (slug: string) => router.push(`/speakers/${encodeURIComponent(slug)}`)
  const goNext = () => next.value && open(next.value.speaker.slug)

  function playCursor(): boolean {
    const s = cursorRow.value?.speaker
    if (!s?.sample) return false
    audio.play(s.sample, undefined, { title: s.name, subtitle: s.sample })
    return true
  }

  function onKey(e: KeyboardEvent) {
    if (locked.value || e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return
    const k = e.key.toLowerCase()
    if (k === KEY_DOWN || k === KEY_UP) move(k === KEY_DOWN ? 1 : -1)
    else if (k === KEY_NEXT) goNext()
    else if (e.key === 'Enter' && cursor.value && !(e.target as HTMLElement | null)?.closest?.('a, button')) open(cursor.value)
    else if (e.key === ' ' && playCursor()) e.preventDefault()
    else return
    if (k === KEY_DOWN || k === KEY_UP || k === KEY_NEXT) e.preventDefault()
  }
  onMounted(() => {
    document.addEventListener('keydown', onKey)
    void store.load()
    void store.loadSlotLines()
  })
  onBeforeUnmount(() => document.removeEventListener('keydown', onKey))

  return { store, q, show, cursor, counts, next, groups, totals, slotLineTotal, shown, goNext, open }
}
