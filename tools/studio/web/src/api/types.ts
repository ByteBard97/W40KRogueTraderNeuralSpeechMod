export type Origin = 'real' | 'designed' | 'supplied'
export type SpeakerStatus = 'needs_voice' | 'source' | 'profile'
export type ModelState = 'down' | 'ready' | 'busy'

export interface SpeakerSummary {
  slug: string
  name: string
  origin: 'real' | 'designed'
  line_count: number
  status: SpeakerStatus
  has_pick: boolean
  /** Added by the list enrichment; optional so an older server still renders. */
  kind?: 'named' | 'slot' | 'real'
  pick?: string | null
  ranked?: number
  candidates?: number
  registered?: boolean
  sample?: string | null
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
  /** 1 to 5, null clears it. Separate from fit; stored by the studio in audit.json. */
  accent_score?: number | null
  reject?: boolean
}

export interface Candidate {
  id: string
  file: string
  scores: { p_us: number; top: string; p_top: number } | null
  verdict: Verdict
  gen: { seed?: number; cfg?: number; timesteps?: number; live?: boolean } | null
}

export interface CloneTest {
  file: string
  candidate: string | null
  text: string
  scores: { p_us: number; top?: string; p_top?: number } | null
}

export interface RegisterAllResult {
  registered: { name: string; cand: string | null }[]
  skipped: { name: string; reason: 'no_pick' | 'real' | 'error' | string; detail?: string }[]
}

export interface DesignState {
  description: string
  text: string
  candidates: Candidate[]
  order: string[]
  pick: string | null
  clones: CloneTest[]
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
  /** Seconds of the bank render, when the server reports it. */
  dur?: number | null
}

export interface TakeFx {
  presets: string[]
  wav: string
  v: number
  /** Seconds of the processed clip, when the server reports it. */
  dur?: number | null
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
  /** Made by hand with 'New designed voice'. */
  custom?: boolean
}

export interface PoolSummary {
  threshold: number
  built: string
  total: number
  destinations: { narrator: number; speaker_bank: number; speaker_nobank: number; slot: number }
  slots: PoolSlot[]
  queue_lines: number
  queue_entries: number
  /** Routes set by hand (source 'override'). */
  overrides?: number
}

/** A line sampled for review. `wav` is repo-relative (servable via /file), null when not rendered. */
export interface PoolSampleItem {
  guid: string
  text: string
  wav: string | null
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
  role?: string | null
  sample_items?: PoolSampleItem[]
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
  entry_name?: string | null
  entry_label?: string | null
  wav?: string | null
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
  items: { guid: string; text: string; entry: string | null; wav?: string | null }[]
}

/** What `override` returns. `undo.previous` goes back to `/routes/restore`. Absent on an older server. */
export interface OverrideResult {
  changed: number
  undo?: { previous: Record<string, unknown> }
}

export interface NewSlotBody {
  name: string
  gender: 'male' | 'female' | 'any'
  species?: string
  age?: string
  description?: string
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
  /** Added by the redesign API; older servers omit them. */
  family?: string
  version?: string
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
  backup?: string | null
  affected_speakers?: number
}

export interface FxUsage {
  labels: Record<string, { lines: number; speakers: number; presets: number }>
  pools_built: boolean
}

export interface FxDiffRow {
  voice: string
  kind: string
  speaker: string
  labels: string[]
  lines: number
  now: string[]
  after: string[]
  changed: boolean
  changed_lines: number
  sample_wav: string | null
}

export interface FxDiff {
  rows: FxDiffRow[]
  changed: number
  unmapped_labels: Record<string, number>
  file_mtime: number | null
}

export interface FxBackup {
  name: string
  kind: 'assignments' | 'labels'
  path: string
  mtime: number
  size: number
}

export interface FxRestored {
  restored: string
  kind: string
  path: string
  backup: string | null
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
  /** Added by the server's matches change (API-CHANGES): absent on an older server. */
  suggest?: 'accept' | 'reject'
  suggest_reason?: string
  /** Repo path of a prompt-bank clip of the proposed speaker; null without a bank. */
  speaker_sample?: string | null
}

export interface MatchCounts {
  flagged: number
  bank: number
  nobank: number
  undecided: number
  total?: number
  accepted?: number
  rejected?: number
  reviewed?: number
  unreviewed?: number
  flagged_unreviewed?: number
}

export interface MatchesPage {
  total: number
  offset: number
  limit: number
  counts: MatchCounts
  items: MatchRowData[]
  /** A deferred pools rebuild is pending. */
  pools_stale?: boolean
}

export interface MatchFilter {
  group?: string
  speaker?: string
  state?: string
  q?: string
}

export type QaVerdictValue = 'good' | 'bad'

export interface QaVerdict {
  verdict: QaVerdictValue
  tags: string[]
  note: string
}

export interface QaRun {
  id: string
  label: string
  clips: number
}

export interface QaFacets {
  speakers: string[]
  refs: string[]
  engines: string[]
  flags: string[]
}

export interface QaClip {
  guid: string
  wav: string
  text: string
  context: string
  speaker: string
  engine: string
  voice_source: string
  dur: number
  cps: number
  emotion: string
  instruct: string
  ref_path: string
  ref: string
  real: QaRealClip[]
  old: string | null
  heard: string
  wer: number | null
  flags: string[]
  verdict: QaVerdict | null
}

export interface QaRealClip {
  label: string
  path: string
  text: string
  full_line: boolean
}

export interface QaRefTally {
  good: number
  bad: number
  total: number
}

export interface QaStats {
  good: number
  bad: number
  unjudged: number
  by_ref?: Record<string, QaRefTally>
}

/** Counts for the filtered set (not the whole run). Sent by newer servers only. */
export interface QaView {
  good: number
  bad: number
  unjudged: number
  total: number
}

export interface QaPage {
  view?: QaView
  total: number
  offset: number
  limit: number
  items: QaClip[]
  stats: QaStats
}

export type QaSort = 'suspicious' | 'slowest' | 'fastest' | 'longest' | 'shortest' | 'random'
export type QaFx = 'mild' | 'strong'

export interface QaFilter {
  speaker?: string
  ref?: string
  engine?: string
  flag?: string
  verdict?: string
  q?: string
  sort?: QaSort
  seed?: number
}

export interface QaVerdictBody {
  run: string
  guid: string
  verdict: QaVerdictValue | null
  tags: string[]
  note: string
}

export interface CastSuggestion { slug: string; name: string; lines: number; gender: string; f0: number | null; used_by: string[] }
export interface CastCharacter {
  speaker: string
  /** What to show: the character's name, or the group's name for a nameless group. */
  display: string
  kind: 'character' | 'slot'
  rank: number | null
  lines: number
  chars: number
  approx_minutes: number
  status: 'designed' | 'voiceless'
  gender: string | null
  species: string | null
  age: string | null
  role: string | null
  voice_description: string | null
  pool_slot: string | null
  samples: string[]
  portrait: string | null
  portrait_name: string | null
  portrait_chosen: boolean
  assignment: { bg3: string; name: string } | null
  suggestions: CastSuggestion[]
}
export interface CastPage { characters: CastCharacter[]; total: number; assigned: number; portraits: string[] }
export interface Bg3Ref { wav: string; text: string; seconds: number; speech_seconds?: number; speech_ratio?: number; kind?: 'single' | 'stitched' }
export interface Bg3Voice { slug: string; name: string; lines: number; minutes: number; gender: string; f0: number | null; non_human: boolean; refs: Bg3Ref[]; used_by: string[]; aliases?: string[]; quality?: 'good' | 'ok' | 'poor' | null; labels: VoiceLabels; mine: VoiceLabels; complete: boolean }
export interface CastAudition { file: string; text: string; seconds: number | null; ref: string }
export interface CastRegistered { registered: string[]; skipped: string[] }

export type LabelValue = string | string[]
export type VoiceLabels = Record<string, LabelValue | undefined>
export interface LabelDef { key: string; label: string; kind: 'single' | 'multi' | 'text' | 'rating'; options: string[]; required: boolean; allow_several?: boolean }
export interface LabelProgress { total: number; complete: number; started: number }
export interface LabelsInfo { schema: LabelDef[]; progress: LabelProgress }

export type AssignmentStatus = 'assigned' | 'needs_info' | 'no_voice'
export interface AssignmentAlt { bg3: string; score: number | null; name: string }
export interface AssignmentResearch { conversation: string | null; comment: string; lines: { say: string; after: string }[]; narration: string[]; nearby: string }
export interface AssignmentItem {
  key: string; kind: 'character' | 'group'; name: string; guessed_name?: string | null; gender: string | null; species: string | null; age: string | null
  role: string; description: string; lines: number; conversation: string | null; status: AssignmentStatus
  bg3?: string; voice_name?: string | null; owner?: boolean; processed?: boolean; steps?: number; score?: number | null; reasons?: string[]
  alts: AssignmentAlt[]; missing?: string[]; learned?: Record<string, string>; samples: string[]; research: AssignmentResearch | null
}
export interface AssignmentsPage { generated_at: string | null; summary: Record<string, number>; items: AssignmentItem[] }
export interface RegisterPlanItem { key: string; bg3: string; voice_name: string; clip: string; processed: boolean; steps: number | null; action: 'add' | 'update' | 'unchanged' }
export interface RegisterSkipped { key: string; bg3: string; reason: string }
export interface RegisterCounts { assigned: number; not_assigned: number; add: number; update: number; unchanged: number; skipped: number; processed: number }
export interface RegisterPreview { counts: RegisterCounts; items: RegisterPlanItem[]; skipped: RegisterSkipped[] }
export interface RegisterResult { registered: string[]; unchanged: number; skipped: RegisterSkipped[]; backup: string | null }
export interface RtVoicesPage { voices: Bg3Voice[]; schema: LabelDef[]; progress: LabelProgress }

// Pedalboard (routes /api/pedalboard/*). Graph and catalog shapes live in src/pedalboard/types.ts.
export interface PedalboardBlocks { lib: string; catalog: import('../pedalboard/types').Catalog }
export interface PedalboardGraphInfo { name: string; updated: number | string }
export interface PedalboardStarter {
  slug: string
  name: string
  description: string
  category: string
  graph: import('../pedalboard/types').Graph
}
export interface PedalboardSaveBody {
  graph: import('../pedalboard/types').Graph
  code: string
  params: Record<string, number>
  notes?: string
}
export interface PedalboardSaved { name: string; dsp: string; saved: boolean }
