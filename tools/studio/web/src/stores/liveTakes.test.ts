import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useLiveTakesStore } from './liveTakes'

const take = (file: string) => ({ file, seed: 1, cfg: 2, timesteps: 10, seconds: 1, description: 'd', text: 't' })

describe('live takes store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('keeps takes per speaker, newest first, across lookups', () => {
    const s = useLiveTakesStore()
    s.add('a', take('1'))
    s.add('a', take('2'))
    s.add('b', take('3'))
    expect(s.forSlug('a').map((t) => t.file)).toEqual(['2', '1'])
    expect(s.forSlug('b')).toHaveLength(1)
    expect(s.forSlug('zzz')).toEqual([])
  })

  it('removes one take', () => {
    const s = useLiveTakesStore()
    const t = s.add('a', take('1'))
    s.add('a', take('2'))
    s.remove('a', t)
    expect(s.forSlug('a').map((x) => x.file)).toEqual(['2'])
  })
})

describe('live takes store, duplicates', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('ignores a take whose file is already listed (a job result can arrive twice)', () => {
    const s = useLiveTakesStore()
    s.add('a', take('1'))
    s.add('a', take('1'))
    expect(s.forSlug('a')).toHaveLength(1)
  })
})
