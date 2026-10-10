import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useToasts } from '../../composables/useToasts'
import BusyJobCard from './BusyJobCard.vue'
import DataRow from './DataRow.vue'
import InlineConfirm from './InlineConfirm.vue'
import InlineError from './InlineError.vue'
import Skeleton from './Skeleton.vue'
import ToastStack from './ToastStack.vue'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'

describe('SectionCard summary', () => {
  it('keeps the summary visible when closed and sets aria-expanded', async () => {
    const w = mount(SectionCard, { props: { title: 'Options', summary: 'cfg 2', collapsedByDefault: true, step: 3 }, slots: { default: '<p class="b">x</p>' } })
    expect(w.text()).toContain('cfg 2')
    expect(w.find('.toggle').attributes('aria-expanded')).toBe('false')
    await w.find('.toggle').trigger('click')
    expect(w.find('.b').exists()).toBe(true)
    expect(w.find('.toggle').attributes('aria-expanded')).toBe('true')
  })
  it('actions do not toggle the card', async () => {
    const w = mount(SectionCard, { props: { title: 'T' }, slots: { actions: '<button class="a">go</button>' } })
    await w.find('.a').trigger('click')
    expect(w.find('.body').exists()).toBe(true)
  })
})

describe('DataRow', () => {
  it('renders slots and marks the selected row', () => {
    const w = mount(DataRow, { props: { selected: true }, slots: { lead: '<i class="l"/>', default: 'Name', end: '<b class="e"/>' } })
    expect(w.classes()).toContain('sel')
    expect(w.attributes('aria-current')).toBe('true')
    expect(w.find('.l').exists() && w.find('.e').exists() && w.text() === 'Name').toBe(true)
  })
})

describe('toasts', () => {
  beforeEach(() => useToasts().clear())
  it('shows an undo toast and runs the action on click and on Z', async () => {
    const undo = vi.fn()
    const w = mount(ToastStack, { attachTo: document.body })
    useToasts().undo('Merged', undo)
    await nextTick()
    expect(w.text()).toContain('Merged')
    await w.findAll('button').find((b) => b.text().startsWith('Undo'))!.trigger('click')
    expect(undo).toHaveBeenCalledTimes(1)
    useToasts().undo('Again', undo)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', bubbles: true }))
    expect(undo).toHaveBeenCalledTimes(2)
    w.unmount()
  })
  it('error toasts are alerts with a Retry action', async () => {
    const w = mount(ToastStack)
    useToasts().error('Not saved', () => {})
    await nextTick()
    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(w.text()).toContain('Retry')
  })
})

describe('InlineError / InlineConfirm', () => {
  it('error is an alert with a title', () => {
    const w = mount(InlineError, { props: { title: 'File not found' }, slots: { default: '<i>detail</i>' } })
    expect(w.attributes('role')).toBe('alert')
    expect(w.text()).toContain('File not found')
  })
  it('confirm states the consequence; Enter confirms and Esc cancels', async () => {
    const w = mount(InlineConfirm, { props: { confirmLabel: 'Merge' }, slots: { default: '55 lines move' }, attachTo: document.body })
    expect(w.text()).toContain('55 lines move')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(w.emitted('confirm')).toHaveLength(1)
    expect(w.emitted('cancel')).toHaveLength(1)
    await w.findAll('button')[0].trigger('click')
    expect(w.emitted('confirm')).toHaveLength(2)
    w.unmount()
  })
})

describe('BusyJobCard', () => {
  it('shows progress, elapsed and cancels', async () => {
    const w = mount(BusyJobCard, { props: { title: 'Generating', elapsedS: 7, progress: 0.42, etaS: 21, cancelable: true } })
    expect(w.text()).toContain('0:07 elapsed')
    expect(w.text()).toContain('~0:21 left')
    expect(w.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('42')
    await w.find('button').trigger('click')
    expect(w.emitted('cancel')).toBeTruthy()
  })
  it('is indeterminate without progress', () => {
    const w = mount(BusyJobCard, { props: { title: 'x', elapsedS: 1 } })
    expect(w.find('.indeterminate').exists()).toBe(true)
  })
})

describe('Skeleton / EmptyState', () => {
  it('renders the requested rows', () => expect(mount(Skeleton, { props: { rows: 4 } }).findAll('.skeleton')).toHaveLength(4))
  it('empty, loading and error variants', () => {
    expect(mount(EmptyState, { props: { message: 'none' } }).text()).toBe('none')
    expect(mount(EmptyState, { props: { state: 'loading', title: 'Loading' } }).find('.spinner').exists()).toBe(true)
    expect(mount(EmptyState, { props: { state: 'error', title: 'Bad' } }).attributes('role')).toBe('alert')
  })
})
