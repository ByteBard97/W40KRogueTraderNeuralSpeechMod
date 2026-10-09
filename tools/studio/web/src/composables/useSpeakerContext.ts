import { inject, provide, type InjectionKey } from 'vue'
import type { SpeakerContext } from './useSpeakerState'

export const SPEAKER_CTX_KEY: InjectionKey<SpeakerContext> = Symbol('speakerContext')

export const provideSpeakerContext = (ctx: SpeakerContext) => provide(SPEAKER_CTX_KEY, ctx)

export function useSpeakerContext(): SpeakerContext {
  const ctx = inject(SPEAKER_CTX_KEY)
  if (!ctx) throw new Error('useSpeakerContext must be used inside a speaker page')
  return ctx
}
