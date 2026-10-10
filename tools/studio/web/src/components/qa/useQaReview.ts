import { computed, ref, watch } from 'vue'
import type { QaFilter, QaFx, QaVerdictValue } from '../../api/types'
import { useToasts } from '../../composables/useToasts'
import { useNavCountsStore } from '../../stores/navCounts'
import { QA_PAGE, useQaStore } from '../../stores/qa'
import { COMPRESSOR_KEY, QA_TAGS, tagIndex, type QaAction } from '../../utils/qaKeys'

type FxChoice = QaFx | ''
const FX_CHOICES: QaFx[] = ['mild', 'strong']
/** How close to the end of the loaded queue the cursor may get before the next batch is fetched. */
const PREFETCH_MARGIN = 3
const EXPORT_RUN = 'export'

function savedFx(): FxChoice {
  try {
    const v = localStorage.getItem(COMPRESSOR_KEY)
    return FX_CHOICES.includes(v as QaFx) ? (v as QaFx) : ''
  } catch { return '' }
}

/** Review-mode behaviour for Render QA: the cursor, verdicts with undo, tags, compressor and the loading around them. */
export function useQaReview() {
  const qa = useQaStore()
  const toasts = useToasts()
  const navCounts = useNavCountsStore()

  const fx = ref<FxChoice>(savedFx())
  let lastFx: QaFx = fx.value || 'mild'
  watch(fx, (v) => {
    if (v) lastFx = v
    try { localStorage.setItem(COMPRESSOR_KEY, v) } catch { /* private window: the choice just is not remembered */ }
  })

  const position = computed(() => (qa.items.length ? qa.index + 1 : 0))
  const range = computed(() => qa.items.length)

  async function init() {
    await qa.loadRuns()
    await Promise.all([qa.loadFacets(), qa.loadPage(0)])
  }
  const pickRun = (id: string) => qa.setRun(id)
  const applyFilter = (f: QaFilter) => qa.setFilter(f)

  // Keep the next batch coming so j never runs into the end of the list.
  watch(() => qa.index, (i) => { if (qa.hasNext && i >= qa.items.length - PREFETCH_MARGIN) void qa.loadMore() })
  // The top-bar badge counts what is left to judge in the main export.
  watch(() => [qa.run, qa.stats.unjudged] as const, ([run, left]) => { if (run === EXPORT_RUN) navCounts.qaClips = left })

  function judge(v: QaVerdictValue | null) {
    const c = qa.current
    if (!c) return
    const guid = c.guid
    const before = c.verdict
    void qa.setVerdict(guid, v)
    if (v) qa.move(1)
    if (!v && !before) return
    toasts.undo(v ? `Marked ${v}` : 'Verdict cleared', () => {
      const i = qa.items.findIndex((x) => x.guid === guid)
      if (i >= 0) qa.select(i)
      void qa.setVerdict(guid, before?.verdict ?? null, before?.tags, before?.note)
    })
  }
  const setTags = (guid: string, tags: string[]) => qa.setDetails(guid, tags, qa.items.find((c) => c.guid === guid)?.verdict?.note ?? '')
  const setNote = (guid: string, note: string) => qa.setDetails(guid, qa.items.find((c) => c.guid === guid)?.verdict?.tags ?? [], note)
  function toggleTagAt(i: number) {
    const c = qa.current
    const t = QA_TAGS[i]
    if (!c || !t) return
    const tags = c.verdict?.tags ?? []
    void setTags(c.guid, tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t])
  }
  async function nextUnjudged() {
    const i = await qa.findNextUnjudged(qa.index)
    if (i >= 0) qa.select(i)
    else toasts.ok('No unjudged clips left in this view')
  }

  /** `play` is the card's Space handler. */
  function handler(play: () => void) {
    return (a: QaAction) => {
      const t = tagIndex(a)
      if (t !== null) return toggleTagAt(t)
      const table: Partial<Record<QaAction, () => void>> = {
        next: () => qa.move(1),
        prev: () => qa.move(-1),
        play,
        good: () => judge('good'),
        bad: () => judge('bad'),
        clear: () => judge(null),
        nextUnjudged: () => void nextUnjudged(),
        toggleFx: () => { fx.value = fx.value ? '' : lastFx },
      }
      table[a]?.()
    }
  }

  return { qa, fx, position, range, init, pickRun, applyFilter, judge, setTags, setNote, nextUnjudged, handler, QA_PAGE }
}
