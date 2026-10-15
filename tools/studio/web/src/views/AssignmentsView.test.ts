import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useToasts } from '../composables/useToasts'

vi.mock('../api/client', () => ({ api: { assignments: vi.fn(), assignmentsRun: vi.fn(), assignmentOverride: vi.fn(), castingVoices: vi.fn(), assignmentsRegisterPreview: vi.fn(), assignmentsRegister: vi.fn() } }))

import AssignmentsView from './AssignmentsView.vue'

const preview = { counts: { assigned: 3, not_assigned: 1, add: 2, update: 0, unchanged: 0, skipped: 1, processed: 1 }, items: [], skipped: [{ key: 'Mute', bg3: 'v1', reason: 'the voice has no usable reference clip' }] }

async function make() {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  useToasts().clear()
  vi.mocked(api.assignments).mockResolvedValue({ generated_at: 'x', summary: { assigned: 1 }, items: [] } as never)
  vi.mocked(api.castingVoices).mockResolvedValue([] as never)
  vi.mocked(api.assignmentsRegisterPreview).mockResolvedValue(preview as never)
  const w = mount(AssignmentsView, { attachTo: document.body })
  await flushPromises()
  return w
}

describe('Assignments register flow', () => {
  beforeEach(() => { document.body.innerHTML = '' })

  it('the button shows the preview and the skipped list; nothing is written until confirmed', async () => {
    const w = await make()
    await w.find('[data-register-open]').trigger('click')
    await flushPromises()
    const panel = w.find('[data-register-panel]')
    expect(panel.text()).toContain('This writes the prompt bank')
    expect(panel.text()).toContain('Mute')
    expect(panel.text()).toContain('no usable reference clip')
    expect(api.assignmentsRegister).not.toHaveBeenCalled()
    w.unmount()
  })

  it('Cancel closes the confirm; Register writes and toasts', async () => {
    const w = await make()
    await w.find('[data-register-open]').trigger('click')
    await flushPromises()
    const buttons = () => w.find('[data-register-panel]').findAll('button')
    await buttons().find((b) => b.text().includes('Cancel'))!.trigger('click')
    expect(w.find('[data-register-panel]').exists()).toBe(false)
    vi.mocked(api.assignmentsRegister).mockResolvedValue({ registered: ['a', 'b'], unchanged: 0, skipped: [], backup: null })
    await w.find('[data-register-open]').trigger('click')
    await flushPromises()
    await buttons().find((b) => b.text().includes('Register'))!.trigger('click')
    await flushPromises()
    expect(api.assignmentsRegister).toHaveBeenCalledTimes(1)
    expect(w.find('[data-register-panel]').exists()).toBe(false)
    expect(useToasts().toasts.value[0].message).toContain('Registered 2 voices')
    w.unmount()
  })
})
