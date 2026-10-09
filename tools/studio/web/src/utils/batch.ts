import type { CloneRequest, Line, ModelOptions, SourceClip, Take } from '../api/types'
import { pickSeed } from './seed'

export interface BatchArgs {
  lines: Line[]
  sources: SourceClip[]
  options: ModelOptions
  generate: (req: CloneRequest) => Promise<Take>
  onTake: (t: Take) => void | Promise<void>
  shouldStop?: () => boolean
}

export interface BatchResult {
  done: number
  total: number
  error: string | null
}

/** Every line x every source. One seed per line is shared by all sources so differences come from the source clip. */
export async function runBatch(a: BatchArgs): Promise<BatchResult> {
  const total = a.lines.length * a.sources.length
  let done = 0
  for (const line of a.lines) {
    const seed = pickSeed(a.options.seed)
    for (const src of a.sources) {
      if (a.shouldStop?.()) return { done, total, error: null }
      try {
        const take = await a.generate({
          guid: line.guid,
          text: line.text,
          instruct: line.instruct,
          reference: { wav: src.wav, text: src.text },
          options: { ...a.options, seed },
        })
        await a.onTake(take)
        done++
      } catch (e) {
        return { done, total, error: e instanceof Error ? e.message : String(e) }
      }
    }
  }
  return { done, total, error: null }
}
