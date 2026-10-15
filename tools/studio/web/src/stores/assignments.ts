import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { AssignmentItem, AssignmentsPage, Bg3Voice } from '../api/types'

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))

export type AssignmentFilter = 'all' | 'assigned' | 'needs_info' | 'mine'
export type AssignmentKind = 'character' | 'group' | 'all'

/** The automatic BG3 voice assignments for characters without a voice, for checking and overriding. The server is the source of truth. */
export const useAssignmentsStore = defineStore('assignments', () => {
  const page = ref<AssignmentsPage | null>(null)
  const voices = ref<Bg3Voice[]>([])
  const selected = ref<string | null>(null)
  const status = ref<AssignmentFilter>('all')
  const kind = ref<AssignmentKind>('all')
  const query = ref('')
  const error = ref<string | null>(null)
  const loading = ref(false)
  const running = ref(false)

  const items = computed(() => page.value?.items ?? [])
  const visible = computed(() => {
    const q = query.value.trim().toLowerCase()
    return items.value.filter((i) =>
      (kind.value === 'all' || i.kind === kind.value)
      && (status.value === 'all' || (status.value === 'mine' ? !!i.owner : status.value === 'assigned' ? i.status === 'assigned' : i.status !== 'assigned'))
      && (!q || `${i.name} ${i.role} ${i.voice_name ?? ''} ${i.conversation ?? ''}`.toLowerCase().includes(q)))
  })
  const current = computed<AssignmentItem | null>(() => items.value.find((i) => i.key === selected.value) ?? visible.value[0] ?? null)
  const bySlug = computed(() => new Map(voices.value.map((v) => [v.slug, v])))
  const voiceOf = (i: AssignmentItem | null) => (i?.bg3 ? bySlug.value.get(i.bg3) ?? null : null)
  const summary = computed(() => page.value?.summary ?? {})

  async function load() {
    loading.value = true
    error.value = null
    try {
      const [p, v] = await Promise.all([api.assignments(), api.castingVoices()])
      page.value = p
      voices.value = v
    } catch (e) {
      error.value = msg(e)
    } finally {
      loading.value = false
    }
  }

  const select = (key: string) => { selected.value = key }

  /** Work every assignment out again; the voices you picked yourself stay. */
  async function rerun() {
    running.value = true
    error.value = null
    try {
      await api.assignmentsRun()
      page.value = await api.assignments()
    } catch (e) {
      error.value = msg(e)
    } finally {
      running.value = false
    }
  }

  /** Pick a voice for one item yourself, or with null hand it back to the rules. */
  async function override(key: string, bg3: string | null) {
    error.value = null
    try {
      await api.assignmentOverride(key, bg3)
      page.value = await api.assignments()
    } catch (e) {
      error.value = msg(e)
    }
  }

  return { page, voices, selected, status, kind, query, error, loading, running, items, visible, current, summary, voiceOf, load, select, rerun, override }
})
