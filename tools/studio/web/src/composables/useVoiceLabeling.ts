import { computed, ref } from 'vue'
import type { Bg3Voice, LabelDef, LabelValue } from '../api/types'
import { useCastingStore } from '../stores/casting'
import { DO_NOT_USE, filterVoices, type LabelFilters, type VoiceSort } from '../utils/castVoices'
import { fileUrl } from '../utils/fileUrl'
import { useAudioPlayer } from './useAudioPlayer'

export type LabelingView = 'todo' | 'done' | 'all'

/** What the label page needs from a store of voices: the BG3 voices (casting store) and the Rogue Trader voices (rtVoices store) both fit. */
export interface LabelStore { voices: Bg3Voice[]; schema: LabelDef[]; setLabel: (slug: string, key: string, value: LabelValue | null) => Promise<void> }

/** State of a label page: which voices are listed, which is selected, and the "label it, then move on" flow. */
export function useVoiceLabeling<S extends LabelStore = ReturnType<typeof useCastingStore>>(store: S = useCastingStore() as unknown as S) {
  const audio = useAudioPlayer()
  const view = ref<LabelingView>('todo')
  const query = ref('')
  const sort = ref<VoiceSort>('lines')
  const filters = ref<LabelFilters>({})
  const selected = ref<string | null>(null)
  const autoAdvance = ref(true)
  const autoplay = ref(true)

  const rows = computed(() =>
    filterVoices(store.voices, query.value, 'all', sort.value, filters.value).filter((v) => view.value === 'all' || (view.value === 'done') === v.complete))
  const current = computed(() => store.voices.find((v) => v.slug === selected.value) ?? rows.value[0] ?? null)

  function play(slug: string | undefined) {
    const v = store.voices.find((x) => x.slug === slug)
    if (v?.refs[0]) audio.play(v.refs[0].wav, fileUrl(v.refs[0].wav), { title: v.name })
  }

  function select(slug: string) {
    selected.value = slug
    if (autoplay.value) play(slug)
  }

  /** The voice `step` places along the list from the current one (wraps), or null for an empty list. */
  function neighbour(step: 1 | -1): string | null {
    const list = rows.value
    if (!list.length) return null
    const at = list.findIndex((v) => v.slug === current.value?.slug)
    if (at < 0) return list[step === 1 ? 0 : list.length - 1].slug          // the current voice just left this view (it is done)
    return list[(at + step + list.length) % list.length].slug
  }

  const move = (step: 1 | -1) => { const s = neighbour(step); if (s) select(s) }

  /** The next voice still to label after `slug` in the given order (wraps round), or undefined when all are done. */
  function nextAfter(slug: string, order: string[]) {
    const at = order.indexOf(slug)
    const seq = [...order.slice(at + 1), ...order.slice(0, at + 1)]
    return seq.map((s) => store.voices.find((v) => v.slug === s)).find((v) => v && !v.complete)
  }

  function nextIncomplete() {
    const here = current.value?.slug
    const next = (here ? nextAfter(here, rows.value.map((v) => v.slug)) : undefined) ?? store.voices.find((v) => !v.complete)
    if (next) select(next.slug)
  }

  /** Label the selected voice; once its five required labels are all set, move on to the next one still to do (after it in the list). */
  async function label(key: string, value: Parameters<typeof store.setLabel>[2], forceAdvance = false) {
    const slug = current.value?.slug
    if (!slug) return
    const order = rows.value.map((v) => v.slug)        // the order as it was, before this voice drops out of the "to label" view
    const was = current.value?.complete
    selected.value = slug
    await store.setLabel(slug, key, value)
    if ((autoAdvance.value || forceAdvance) && !was && store.voices.find((v) => v.slug === slug)?.complete) {
      const next = nextAfter(slug, order)
      if (next) select(next.slug)
    }
  }

  /** The "do not use" key: mark the selected voice and move straight on; on a voice already marked, take the mark off and stay. */
  async function toggleSkip() {
    if (!store.schema.some((d) => d.key === 'reserve')) return          // only the BG3 voices have a "use" label
    const skipped = current.value?.mine.reserve === DO_NOT_USE
    await label('reserve', skipped ? null : DO_NOT_USE, true)
  }

  return { store, view, query, sort, filters, selected, autoAdvance, autoplay, rows, current, select, move, nextIncomplete, label, toggleSkip, play }
}
