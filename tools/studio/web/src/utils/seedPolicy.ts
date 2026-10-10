import { pickSeed } from './seed'

export type SeedPolicy = 'new' | 'one' | 'fixed'

export const SEED_POLICY_OPTIONS = [
  { value: 'new', label: 'New seed per line' },
  { value: 'one', label: 'One seed for all' },
  { value: 'fixed', label: 'Fixed…' },
] as const

export const SEED_POLICY_SUMMARY: Record<SeedPolicy, string> = { new: 'new seed per line', one: 'one seed for all', fixed: 'fixed seed' }

/**
 * Seeds for a batch of `lines` lines. Every source ticked for a line shares that line's seed, so differences between sources come from
 * the clip. "new" draws one per line, "one" draws once for the whole batch, "fixed" uses the typed seed (a blank typed seed falls back to "new").
 */
export function seedsFor(policy: SeedPolicy, typed: string, lines: number, rand: () => number = Math.random): string[] {
  if (policy === 'fixed' && typed.trim()) return Array.from({ length: lines }, () => typed.trim())
  if (policy === 'one') return Array.from({ length: lines }, ((s) => () => s)(pickSeed('', rand)))
  return Array.from({ length: lines }, () => pickSeed('', rand))
}
