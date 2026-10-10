import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import ShortcutOverlay from '../components/ui/ShortcutOverlay.vue'
import { useShortcutOverlay, useShortcuts } from './useShortcuts'

const press = (k: string, target: EventTarget = document) => target.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }))

describe('shortcut overlay', () => {
  it('lists the page shortcuts registered through useShortcuts plus the global ones, opens on ? and closes on Esc', async () => {
    const Page = defineComponent({ setup() { useShortcuts({ title: 'Render QA', groups: [{ title: 'Judge', items: [{ label: 'Good', keys: ['G'] }] }] }); return () => null } })
    const page = mount(Page)
    const o = mount(ShortcutOverlay, { attachTo: document.body })
    expect(o.find('[role="dialog"]').exists()).toBe(false)
    press('?')
    await nextTick()
    expect(o.find('[role="dialog"]').attributes('aria-label')).toContain('Render QA')
    expect(o.text()).toContain('Judge')
    expect(o.text()).toContain('Play / pause')
    press('Escape')
    await nextTick()
    expect(o.find('[role="dialog"]').exists()).toBe(false)
    page.unmount()
    o.unmount()
  })
  it('does not open while typing in an input', async () => {
    const o = mount(ShortcutOverlay, { attachTo: document.body })
    const input = document.createElement('input')
    document.body.append(input)
    press('?', input)
    await nextTick()
    expect(useShortcutOverlay().open.value).toBe(false)
    o.unmount()
  })
})
