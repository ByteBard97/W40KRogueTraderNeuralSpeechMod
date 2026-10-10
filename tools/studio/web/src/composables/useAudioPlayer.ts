import { useGlobalAudio, type PlayMeta } from './globalAudio'

/** Compatibility wrapper over the app-wide player. `playing` is the id of what is playing now, or null. */
export function useAudioPlayer() {
  const g = useGlobalAudio()
  /** `id` names what is playing; `url` overrides where the audio comes from (default: /file for a repo path). */
  const play = (id: string, url?: string, meta?: PlayMeta) => g.play(id, url, meta)
  return { playing: g.playing, play, stop: g.stop }
}
