import type { PoolSlot, PoolSummary, QueueEntry } from '../api/types'

export const slot = (id: string, name: string, over: Partial<PoolSlot> = {}): PoolSlot => ({
  id, name, speaker_key: `pool_${id}`, slug: `pool_${id}`, gender: 'male', species: 'human', age: null, lines: 10, spot: { checked: 0, wrong: 0 }, ...over,
})

export const summaryOf = (slots: PoolSlot[], over: Partial<PoolSummary> = {}): PoolSummary => ({
  threshold: 0.8, built: '2026-10-09 17:21', total: 100,
  destinations: { narrator: 5, speaker_bank: 20, speaker_nobank: 30, slot: 45 },
  slots, queue_lines: 7, queue_entries: 2, overrides: 0, ...over,
})

export const entryOf = (key: string, over: Partial<QueueEntry> = {}): QueueEntry => ({
  key, entry: `C|${key}`, conversation: 'C', label: `Label ${key}`, name: `Name ${key}`, attr: { gender: 'male', species: 'human', age: 'adult' }, role: null,
  reasons: ['gender low confidence'], lines: 3, samples: ['First line.'], sample_items: [{ guid: `g-${key}`, text: 'First line.', wav: `data/render/export/${key}.wav` }],
  to: 'slot', slot: 'male_human', speaker: null, evidence: ['evidence one'], ...over,
})
