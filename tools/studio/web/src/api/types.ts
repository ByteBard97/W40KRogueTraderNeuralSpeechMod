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

export type PoolTarget = 'speaker' | 'narrator' | 'slot'

export interface PoolSlot {
  id: string
  name: string
  speaker_key: string
  slug: string
  gender: string
  species: string
  age: string | null
  lines: number
  spot: { checked: number; wrong: number }
}

export interface PoolSummary {
  threshold: number
  built: string
  total: number
  destinations: { narrator: number; speaker_bank: number; speaker_nobank: number; slot: number }
  slots: PoolSlot[]
  queue_lines: number
  queue_entries: number
}

export interface QueueEntry {
  key: string
  entry: string | null
  conversation: string | null
  label: string
  name: string | null
  attr: { gender: string; species: string; age: string } | null
  reasons: string[]
  lines: number
  samples: string[]
  to: PoolTarget
  slot?: string | null
  speaker?: string | null
  evidence: string[]
}

export interface PoolRoute {
  guid: string
  text: string
  to: PoolTarget
  speaker?: string
  has_bank?: boolean
  slot?: string
  entry: string | null
  confidence: number | null
  reasons: string[]
  source: 'auto' | 'override'
}

export interface RoutesPage {
  total: number
  offset: number
  limit: number
  items: PoolRoute[]
}

export interface SpotSample {
  slot: string
  size: number
  remaining: number
  items: { guid: string; text: string; entry: string | null }[]
}

export interface OverrideBody {
  entry?: string
  guids?: string[]
  to?: PoolTarget
  slot?: string
  speaker?: string
}

export interface FxPresetInfo {
  name: string
  source: 'scenario' | 'saved'
  dsp: string
  notes: string
}

export type FxLabels = Record<string, string[]>

export interface FxPreview {
  lines: number
  speakers: number
  unmapped_labels: Record<string, number>
  sample: { guid: string; presets: string[] }[]
}

export interface FxWritten {
  path: string
  lines: number
  speakers: number
}

export type MatchValue = '' | 'accept' | 'reject'

export interface MatchRowData {
  id: string
  conversation: string
  entry: string
  name: string | null
  label: string | null
  gender: string | null
  species: string | null
  role: string | null
  evidence: string[]
  lines: number
  samples: string[]
  gaps: boolean[]
  speaker: string
  has_bank: boolean
  speaker_lines: number
  game_gender: string | null
  warning: string | null
  ambiguous_with: string[] | null
  flagged: boolean
  decision: MatchValue
  effective: MatchValue
}

export interface MatchesPage {
  total: number
  offset: number
  limit: number
  counts: { flagged: number; bank: number; nobank: number; undecided: number }
  items: MatchRowData[]
}

export interface MatchFilter {
  group?: string
  speaker?: string
  state?: string
  q?: string
}
