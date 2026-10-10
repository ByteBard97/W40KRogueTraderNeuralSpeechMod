import { describe, expect, it } from 'vitest'
import { NARRATOR_VALUE, parseTarget, routeValue, slotValue, speakerValue, targetLabel, targetOptions } from './poolTargets'

const slots = [{ id: 'male_human', name: 'Male human' }]

describe('poolTargets', () => {
  it('round-trips slot, speaker and narrator values', () => {
    expect(parseTarget(slotValue('male_human'))).toEqual({ to: 'slot', slot: 'male_human' })
    expect(parseTarget(speakerValue('Idira'))).toEqual({ to: 'speaker', speaker: 'Idira' })
    expect(parseTarget(NARRATOR_VALUE)).toEqual({ to: 'narrator' })
    expect(parseTarget('__new__')).toBeNull()
  })
  it('derives the value of an existing route', () => {
    expect(routeValue({ to: 'slot', slot: 'a' })).toBe('slot:a')
    expect(routeValue({ to: 'speaker', speaker: 'X' })).toBe('speaker:X')
    expect(routeValue({ to: 'narrator' })).toBe('narrator')
  })
  it('names a target for buttons and toasts', () => {
    expect(targetLabel('slot:male_human', slots)).toBe('Male human')
    expect(targetLabel('narrator', slots)).toBe('Narrator')
  })
  it('lists slots, the game voice and narrator', () => {
    expect(targetOptions(slots, 'Idira').map((o) => o.label)).toEqual(['Male human', 'Idira (game voice)', 'Narrator'])
    expect(targetOptions(slots).map((o) => o.label)).toEqual(['Male human', 'Narrator'])
  })
})
