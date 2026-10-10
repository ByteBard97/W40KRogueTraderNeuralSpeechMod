import type { OverrideBody, PoolSlot, PoolTarget } from '../api/types'

/** Where a line can be sent, as one string so it fits a <select> value. */
export const NARRATOR_VALUE = 'narrator'
export const NEW_VOICE_VALUE = '__new__'
const SLOT_PREFIX = 'slot:'
const SPEAKER_PREFIX = 'speaker:'

export type MoveTarget = Pick<OverrideBody, 'to' | 'slot' | 'speaker'>
type Slotish = Pick<PoolSlot, 'id' | 'name'>

export const slotValue = (id: string) => `${SLOT_PREFIX}${id}`
export const speakerValue = (key: string) => `${SPEAKER_PREFIX}${key}`

/** Current route of a queue entry or route row, as a select value. */
export function routeValue(r: { to: PoolTarget; slot?: string | null; speaker?: string | null }): string {
  if (r.to === 'slot' && r.slot) return slotValue(r.slot)
  if (r.to === 'speaker' && r.speaker) return speakerValue(r.speaker)
  return NARRATOR_VALUE
}

/** Select value back to an override target; null for the "new voice" marker and unknown values. */
export function parseTarget(value: string): MoveTarget | null {
  if (value === NARRATOR_VALUE) return { to: 'narrator' }
  if (value.startsWith(SLOT_PREFIX)) return { to: 'slot', slot: value.slice(SLOT_PREFIX.length) }
  if (value.startsWith(SPEAKER_PREFIX)) return { to: 'speaker', speaker: value.slice(SPEAKER_PREFIX.length) }
  return null
}

/** Human name of a select value: the slot's name, the game voice, or Narrator. */
export function targetLabel(value: string, slots: Slotish[]): string {
  const t = parseTarget(value)
  if (t?.to === 'slot') return slots.find((s) => s.id === t.slot)?.name ?? t.slot ?? 'slot'
  if (t?.to === 'speaker') return t.speaker ?? 'speaker'
  return 'Narrator'
}

export interface TargetOption { value: string; label: string }

/** Slots, an optional game voice (the entry's own speaker), then Narrator. */
export function targetOptions(slots: Slotish[], speaker?: string | null): TargetOption[] {
  return [
    ...slots.map((s) => ({ value: slotValue(s.id), label: s.name })),
    ...(speaker ? [{ value: speakerValue(speaker), label: `${speaker} (game voice)` }] : []),
    { value: NARRATOR_VALUE, label: 'Narrator' },
  ]
}
