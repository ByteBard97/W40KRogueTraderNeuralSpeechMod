/** Shapes of the render lab API (`/api/lab/*`, see studio_server/lab.py). */
export type LabInstruct = 'annotation' | 'none' | 'custom'
export type LabPronMode = 'arpabet' | 'plain' | 'literal'
export type LabSplitMode = 'whole' | 'sentence' | 'clause' | 'max'
export type LabFlag = 'overdriven' | 'clipped' | 'empty' | null

export interface LabPronunciation { word: string; mode: LabPronMode; value: string }
export interface LabSplit { mode: LabSplitMode; max_chars: number; min_chars: number }

/** The whole experiment. A take keeps the recipe it was made with. */
export interface LabRecipe {
  name: string
  cfg: number
  timesteps: number
  normalize: boolean
  retry_badcase: boolean
  retry_ratio: number | null
  instruct: LabInstruct
  instruct_text: string
  clean: boolean
  lexicon: boolean
  pronunciation: LabPronunciation[]
  punctuation: Record<string, string>
  pause_ms: number
  gaps_ms: Record<string, number>
  split: LabSplit
  /** Blank = random. */
  seed: string
  peak_limit_db: number | null
  level_match: boolean
  trim_silence: boolean
  onset_soften_db: number
  onset_soften_ms: number
}

export interface LabOptions {
  default_recipe: LabRecipe
  marks: string[]
  actions: string[]
  splits: LabSplitMode[]
  defaults: { punctuation: Record<string, string>; gaps_ms: Record<string, number>; split: LabSplit; pause_ms: number }
}

export interface LabSpeaker { speaker: string; slug: string; lines: number; chars: number }
export interface LabRef { wav: string; text?: string; [k: string]: unknown }

export interface LabMetrics { seconds: number; peak_db: number; crest_db: number | null; clip_runs: number; clipped_samples?: number; flag: LabFlag }
export interface LabCurrent extends LabMetrics { wav: string }
export interface LabLine {
  guid: string
  cue: string
  order: number
  text: string
  chars: number
  instruct: string | null
  ref: LabRef
  current: LabCurrent | null
}
export interface LabLines { speaker: string; ref: LabRef | null; lines: LabLine[] }

export interface LabStage { name: string; text: string }
export interface LabPiece { text: string; kind: string; gap_ms: number | null; display: string }
export interface LabPrepared { stages: LabStage[]; pieces: LabPiece[]; recipe: LabRecipe }

export interface LabTakePiece { text: string; seconds: number; crest_db: number | null; flag: LabFlag; level_db?: number | null }
export interface LabTake {
  id: string
  guid: string | null
  label: string
  text: string
  recipe: LabRecipe
  seed: number
  pieces: LabTakePiece[]
  wav: string
  metrics: LabMetrics & { model_peak: number }
  created: string
  rating: number
  note: string
}

export type LabJobState = 'queued' | 'running' | 'done' | 'error' | 'cancelled'
export interface LabJob { id: string; state: LabJobState; total: number; done: number; take_ids: string[]; error: string | null }

export interface LabRenderItem { guid?: string; text?: string; label?: string }
export interface LabRenderBody { speaker: string; items: LabRenderItem[]; recipe: LabRecipe; seeds: number[]; ref?: LabRef }
export interface LabLexiconHit { word: string; ipa: string | null; respell: string | null; arpabet: string | null; voxcpm2: string | null; as_sent: string }
export interface LabRealClip { speaker: string; wav: string; seconds: number; text: string }
export interface LabOpusPreview { kbps: number; wav: string; opus_bytes: number; source_bytes: number; ratio: number }
