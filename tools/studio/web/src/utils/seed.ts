const SEED_RANGE = 2 ** 31

export function pickSeed(input: string, rand: () => number = Math.random): string {
  const typed = input.trim()
  return typed || String(Math.floor(rand() * SEED_RANGE))
}
