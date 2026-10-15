import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import type { ReferenceData } from '../../api/referenceApi'
import MonitorPanel from './MonitorPanel.vue'

const ref = (stereo: ReferenceData['stereo']): ReferenceData => ({ speaker: 'Abelard', freqs: [100, 1000], db: [0, -3], clips_used: 5, stereo })
const text = (w: ReturnType<typeof mount>, id: string) => w.get(`[data-test="${id}"]`).text()

afterEach(() => { vi.restoreAllMocks() })

describe('MonitorPanel', () => {
  it('shows dashes with no signal and no reference', () => {
    const w = mount(MonitorPanel, { props: { taps: null, reference: null, running: false } })
    for (const id of ['st-corr', 'st-width', 'st-bal', 'rf-corr', 'rf-width']) expect(text(w, id)).toBe('-')
  })

  it('renders yours versus game from injected stats', async () => {
    const w = mount(MonitorPanel, { props: { taps: null, reference: ref({ corr: 0.42, side_mid_db: -7.25, ild_sd_db: 1, clips: 3 }), running: false } })
    ;(w.vm as unknown as { stats: unknown }).stats = { corr: 0.9, sideMidDb: -12.34, balanceDb: 1.5 }
    await nextTick()
    expect(text(w, 'st-corr')).toBe('0.90')
    expect(text(w, 'st-width')).toBe('-12.3')
    expect(text(w, 'st-bal')).toBe('1.5')
    expect(text(w, 'rf-corr')).toBe('0.42')
    expect(text(w, 'rf-width')).toBe('-7.3')
  })

  it('says mono for a reference without stereo stats', () => {
    const w = mount(MonitorPanel, { props: { taps: null, reference: ref(null), running: false } })
    expect(text(w, 'rf-corr')).toBe('mono')
    expect(text(w, 'rf-width')).toBe('mono')
  })

  it('reset clears the average readout', async () => {
    const w = mount(MonitorPanel, { props: { taps: null, reference: null, running: false } })
    const vm = w.vm as unknown as { stats: unknown; resetAverage: () => void }
    vm.stats = { corr: 1, sideMidDb: -30, balanceDb: 0 }
    await nextTick()
    expect(text(w, 'st-corr')).toBe('1.00')
    await w.get('[data-test="reset"]').trigger('click')
    expect(text(w, 'st-corr')).toBe('-')
    vm.stats = { corr: 1, sideMidDb: -30, balanceDb: 0 }
    vm.resetAverage()
    await nextTick()
    expect(text(w, 'st-bal')).toBe('-')
  })

  it('runs no animation loop unless running', async () => {
    const raf = vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 1)
    const w = mount(MonitorPanel, { props: { taps: null, reference: null, running: false } })
    expect(raf).not.toHaveBeenCalled()
    await w.setProps({ running: true })
    expect(raf).toHaveBeenCalledTimes(1)
    w.unmount()
  })
})
