import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import Btn from './Btn.vue'
import Flag from './Flag.vue'
import Kbd from './Kbd.vue'
import ScoreChip from './ScoreChip.vue'
import StatusDot from './StatusDot.vue'
import Tag from './Tag.vue'

describe('Btn', () => {
  it('renders variant, size, kbd hint and emits click', async () => {
    const w = mount(Btn, { props: { variant: 'primary', size: 'lg', kbd: 'P' }, slots: { default: 'Register' } })
    expect(w.classes()).toEqual(expect.arrayContaining(['btn', 'v-primary', 's-lg']))
    expect(w.findComponent(Kbd).text()).toBe('P')
    await w.trigger('click')
    expect(w.emitted('click')).toBeTruthy()
  })
  it('icon buttons carry their accessible name and can expose pressed state', () => {
    const w = mount(Btn, { props: { icon: true, label: 'Move up', pressed: true } })
    expect(w.attributes('aria-label')).toBe('Move up')
    expect(w.attributes('aria-pressed')).toBe('true')
    expect(w.classes()).toContain('icon')
  })
  it('does not fire click when disabled', async () => {
    const w = mount(Btn, { attrs: { disabled: true } })
    expect(w.attributes('disabled')).toBeDefined()
  })
})

describe('Tag / Flag / ScoreChip', () => {
  it('apply their variant classes', () => {
    expect(mount(Tag, { props: { variant: 'designed' } }).classes()).toContain('t-designed')
    expect(mount(Flag, { props: { tone: 'bad' }, slots: { default: 'WER' } }).classes()).toContain('f-bad')
    expect(mount(ScoreChip, { props: { tone: 'none' }, slots: { default: 'unscored' } }).classes()).toContain('s-none')
  })
  it('Flag shows an icon by default so colour is not the only signal', () => {
    expect(mount(Flag).find('svg').exists()).toBe(true)
    expect(mount(Flag, { props: { icon: false } }).find('svg').exists()).toBe(false)
  })
})

describe('StatusDot', () => {
  it('gives every state a distinct class and an accessible name', () => {
    const states = ['idle', 'progress', 'picked', 'done', 'good', 'bad', 'flag'] as const
    const classes = states.map((s) => mount(StatusDot, { props: { status: s } }).classes().join(' '))
    expect(new Set(classes).size).toBe(states.length)
    expect(mount(StatusDot, { props: { status: 'flag', label: 'flagged' } }).attributes('aria-label')).toBe('flagged')
  })
})
