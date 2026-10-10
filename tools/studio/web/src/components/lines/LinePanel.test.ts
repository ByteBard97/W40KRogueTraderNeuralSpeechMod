import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { lineOf, makeCtx, withCtx } from '../../test-utils/speakerCtx'
import LinePanel from './LinePanel.vue'

const long = (n: number) => `Line number ${n} is a fairly long sentence for the spread picker to accept it as a test line.`
const many = (n: number) => Array.from({ length: n }, (_, i) => lineOf(`g${i}`, { text: long(i), emotion: ['neutral', 'amused', 'sad', 'fear', 'angry', 'calm', 'proud', 'happy', 'bitter', 'worried'][i % 10] }))
const mk = (lines = many(30), selected: string[] = []) => {
  const ctx = makeCtx({ lines: ref(lines), selectedLines: ref(new Set(selected)) })
  return { ctx, w: mount(LinePanel, withCtx(ctx)) }
}

describe('LinePanel', () => {
  it('ticks and unticks a line in the shared selection', async () => {
    const { ctx, w } = mk(many(3))
    const box = w.find('.tl input[type=checkbox]')
    await box.setValue(true)
    expect([...ctx.selectedLines.value]).toEqual(['g0'])
    await box.setValue(false)
    expect(ctx.selectedLines.value.size).toBe(0)
  })

  it('summarises ticks per emotion', () => {
    const { w } = mk(many(30), ['g0', 'g1', 'g10'])
    expect(w.text()).toContain('3 of 30 ticked')
    expect(w.text()).toContain('neutral 2')
    expect(w.text()).toContain('amused 1')
  })

  it('filters by emotion chip (with counts) and by search text', async () => {
    const { w } = mk(many(30))
    const chips = w.findAll('.chip')
    expect(chips[0].text()).toContain('all')
    expect(chips[0].text()).toContain('30')
    await chips.find((c) => c.text().startsWith('amused'))!.trigger('click')
    expect(w.findAll('.tl').every((r) => r.text().includes('amused'))).toBe(true)
    await w.find('input[type=search]').setValue('number 2 ')
    expect(w.findAll('.tl')).toHaveLength(1)
    await w.find('input[type=search]').setValue('zzz')
    expect(w.text()).toContain('No line matches')
  })

  it('shows the first page with a position bar, then more, then all', async () => {
    const { w } = mk(many(30))
    expect(w.findAll('.tl')).toHaveLength(8)
    expect(w.text()).toContain('Showing 1–8 of 30')
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.tl')).toHaveLength(28)
    await w.find('[data-all]').trigger('click')
    expect(w.findAll('.tl')).toHaveLength(30)
    expect(w.find('[data-all]').exists()).toBe(false)
  })

  it('folds emotions beyond the top eight into a +n chip that expands them', async () => {
    const { w } = mk(many(30))
    expect(w.find('[data-more-emotions]').text()).toBe('+2')
    expect(w.findAll('.chip')).toHaveLength(9)
    await w.find('[data-more-emotions]').trigger('click')
    expect(w.findAll('.chip')).toHaveLength(11)
  })

  it('"spread" ticks up to six lines across emotions and "clear" empties the selection', async () => {
    const { ctx, w } = mk(many(30))
    await w.find('[data-spread]').trigger('click')
    expect(ctx.selectedLines.value.size).toBe(6)
    await w.find('[data-clear]').trigger('click')
    expect(ctx.selectedLines.value.size).toBe(0)
  })

  it('shows the bank render length, disables play without a bank clip, and shows an empty state', () => {
    const { w } = mk([lineOf('a', { baseline: 'data/b/a.wav', dur: 7.94 }), lineOf('b')])
    expect(w.text()).toContain('7.9 s')
    const plays = w.findAll('.tl .play')
    expect(plays[0].attributes('disabled')).toBeUndefined()
    expect(plays[1].attributes('disabled')).toBeDefined()
    expect(mk([]).w.text()).toContain('No lines for this speaker')
  })
})
