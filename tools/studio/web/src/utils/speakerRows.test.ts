import { describe, expect, it } from 'vitest'
import type { SpeakerSummary } from '../api/types'
import { continueTarget, countRows, kindOf, matchesFilter, toRow } from './speakerRows'

const sp = (o: Partial<SpeakerSummary> & { name: string }): SpeakerSummary => ({ slug: o.name.toLowerCase(), origin: 'designed', line_count: 5, status: 'needs_voice', has_pick: false, ...o })

describe('speakerRows', () => {
  it('derives the kind from the server field, else from origin and the pool_ prefix', () => {
    expect(kindOf(sp({ name: 'a', kind: 'slot' }))).toBe('slot')
    expect(kindOf(sp({ name: 'pool_x' }))).toBe('slot')
    expect(kindOf(sp({ name: 'Idira', origin: 'real' }))).toBe('real')
    expect(kindOf(sp({ name: 'Ruoldo' }))).toBe('named')
  })

  it('words the status by stage', () => {
    expect(toRow(sp({ name: 'A', has_pick: true, pick: 'c2.wav' })).text).toBe('picked c2')
    expect(toRow(sp({ name: 'B', registered: true, has_pick: true, pick: 'c1.wav' })).text).toBe('registered c1')
    expect(toRow(sp({ name: 'C', ranked: 4, candidates: 6 })).text).toBe('4 / 6 ranked')
    expect(toRow(sp({ name: 'D' })).text).toBe('not started')
    expect(toRow(sp({ name: 'E', origin: 'real', status: 'source' })).text).toBe('source set')
    expect(toRow(sp({ name: 'F', origin: 'real', status: 'source', line_count: 0 })).text).toBe('no lines')
    expect(toRow(sp({ name: 'G', origin: 'real', status: 'profile' })).text).toBe('profile saved')
  })

  it('takes slot line counts from Pools, since the list counts 0 for slots', () => {
    expect(toRow(sp({ name: 'pool_x', line_count: 0 }), { pool_x: 120 }).lines).toBe(120)
    expect(toRow(sp({ name: 'Named', line_count: 7 }), { Named: 120 }).lines).toBe(7)
  })

  it('counts stages and filters by name and done state', () => {
    const rows = [sp({ name: 'A', has_pick: true }), sp({ name: 'B', registered: true }), sp({ name: 'C', ranked: 1 }), sp({ name: 'D' })].map((s) => toRow(s))
    expect(countRows(rows)).toMatchObject({ total: 4, done: 2, picked: 1, registered: 1, progress: 1, idle: 1 })
    expect(matchesFilter(rows[0], '', 'done')).toBe(true)
    expect(matchesFilter(rows[3], '', 'done')).toBe(false)
    expect(matchesFilter(rows[3], '', 'todo')).toBe(true)
    expect(matchesFilter(rows[3], 'zz', 'all')).toBe(false)
    expect(matchesFilter(rows[3], ' d ', 'all')).toBe(true)
  })

  it('continues with ranking in progress, else the first unstarted named speaker, never a real one', () => {
    const mk = (...l: SpeakerSummary[]) => l.map((s) => toRow(s))
    expect(continueTarget(mk(sp({ name: 'pool_a' }), sp({ name: 'Named' }), sp({ name: 'Mid', ranked: 2, candidates: 6 })))?.speaker.name).toBe('Mid')
    expect(continueTarget(mk(sp({ name: 'pool_a' }), sp({ name: 'Named' })))?.speaker.name).toBe('Named')
    expect(continueTarget(mk(sp({ name: 'Idira', origin: 'real', status: 'source' }), sp({ name: 'Done', has_pick: true })))).toBeNull()
  })
})
