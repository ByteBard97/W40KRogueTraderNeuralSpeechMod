/** Game-voice reference data for the pedalboard monitor (routes /api/ref/*). */

export interface ReferenceStereo { corr: number; side_mid_db: number; ild_sd_db: number; clips: number }
export interface ReferenceData {
  speaker: string
  freqs: number[]
  db: (number | null)[]
  clips_used: number
  stereo: ReferenceStereo | null
}
export interface RefSpeaker { speaker: string; clips: number }

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`)
  return body as T
}

export const refSpeakers = () => getJson<RefSpeaker[]>('/api/ref/speakers')
export const refLtas = (speaker: string) => getJson<ReferenceData>(`/api/ref/ltas?speaker=${encodeURIComponent(speaker)}`)
