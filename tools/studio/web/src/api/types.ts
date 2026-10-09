export type Origin = 'real' | 'designed' | 'supplied'
export type SpeakerStatus = 'needs_voice' | 'source' | 'profile'
export type ModelState = 'down' | 'ready' | 'busy'

export interface SpeakerSummary {
  slug: string
  name: string
  origin: 'real' | 'designed'
  line_count: number
  status: SpeakerStatus
}

export interface RealClip {
  id: string
  wav: string
  duration: number
  text: string
  curated_rank: number | null
  noise_db: number | null
}

export interface Verdict {
  accent?: 'british' | 'american' | 'other'
  fit?: number
  reject?: boolean
}

export interface Candidate {
  id: string
  file: string
  scores: { p_us: number; top: string; p_top: number } | null
  verdict: Verdict
  gen: { seed?: number; cfg?: number; timesteps?: number; live?: boolean } | null
}

export interface DesignState {
  description: string
  text: string
  candidates: Candidate[]
  order: string[]
  pick: string | null
}

export interface ModelOptions {
  cfg: number
  timesteps: number
  seed: string
  use_instruct: boolean
  retry_badcase: boolean
  normalize: boolean
  continuation: boolean
}

export interface SourceRef {
  wav: string
  text: string
  origin: Origin
}

export interface VoiceProfile {
  name: string
  slug: string
  kind: 'speaker'
  source: SourceRef
  options: ModelOptions
  fx: string[]
  test_lines: string[]
  notes: string
  saved: string
}

export interface SpeakerDetail {
  summary: SpeakerSummary
  clips: RealClip[]
  design: DesignState | null
  profile: VoiceProfile | null
}

export interface Line {
  guid: string
  text: string
  emotion: string | null
  intensity: number | null
  pace: string | null
  instruct: string | null
  baseline: string | null
}

export interface TakeFx {
  presets: string[]
  wav: string
  v: number
}

export interface Take {
  id: string
  raw: string
  text: string
  guid: string | null
  reference: string
  options: ModelOptions
  instruct: string | null
  seed: number
  seconds: number
  audio_s: number | null
  rating: number
  note: string
  fx: TakeFx | null
}

export interface LiveTake {
  file: string
  seed: number
  cfg: number
  timesteps: number
  seconds: number
  audio_s?: number
  description: string
  text: string
}

export interface CloneRequest {
  guid: string | null
  text: string
  instruct: string | null
  reference: { wav: string; text: string }
  options: ModelOptions
}

/** Anything the user can clone from: a real clip, a design candidate, or a supplied wav. */
export interface SourceClip {
  key: string
  label: string
  wav: string
  text: string
  origin: Origin
}
