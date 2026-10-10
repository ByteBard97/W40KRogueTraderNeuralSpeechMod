import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QaProgress from './QaProgress.vue'

const stats = { good: 2, bad: 1, unjudged: 11048, by_ref: { abelard: { good: 2, bad: 1, total: 5 } } }

describe('QaProgress', () => {
  it('shows run-wide counts, the session count and the per-reference tally', () => {
    const w = mount(QaProgress, { props: { stats, view: null, session: 3 } })
    expect(w.find('[data-stats]').text()).toBe('2 good · 1 bad · 11,048 unjudged')
    expect(w.find('[data-session]').text()).toBe('this session 3 judged')
    expect(w.find('[data-ref-tally]').text()).toBe('abelard: 2g/1b/5')
  })

  it('labels the bar by what it covers', () => {
    const run = mount(QaProgress, { props: { stats, view: null, session: 0 } })
    expect(run.text()).toContain('this run')
    const view = mount(QaProgress, { props: { stats, view: { good: 1, bad: 1, unjudged: 2, total: 4 }, session: 0 } })
    expect(view.text()).toContain('this view')
    expect(view.find('[role="img"]').attributes('aria-label')).toBe('this view: 1 good, 1 bad, 2 unjudged')
    expect((view.find('.seg-g').element as HTMLElement).style.width).toBe('25%')
  })

  it('hides the per-reference panel when the run has no tally', () => {
    const w = mount(QaProgress, { props: { stats: { good: 0, bad: 0, unjudged: 1 }, view: null, session: 0 } })
    expect(w.find('.refs').exists()).toBe(false)
  })
})
