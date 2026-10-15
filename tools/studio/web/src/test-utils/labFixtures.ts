import type { LabFlag, LabLine, LabOptions, LabRecipe, LabTake } from '../api/labTypes'

export const recipeFixture = (): LabRecipe => ({
  name: 'production (as rendered)', cfg: 3, timesteps: 10, normalize: false, retry_badcase: false, retry_ratio: null,
  instruct: 'annotation', instruct_text: '', clean: true, lexicon: true, pronunciation: [],
  punctuation: { em_dash: 'keep', en_dash: 'keep', ellipsis: 'keep' }, pause_ms: 250,
  gaps_ms: { sentence: 350, clause: 160, dash: 260, ellipsis: 300, paragraph: 600 },
  split: { mode: 'whole', max_chars: 1200, min_chars: 0 }, seed: '', peak_limit_db: -1, level_match: false, trim_silence: false, onset_soften_db: 0, onset_soften_ms: 150,
})

export const optionsFixture = (): LabOptions => ({
  default_recipe: recipeFixture(), marks: ['em_dash', 'en_dash', 'ellipsis'], actions: ['keep', 'comma', 'period', 'ellipsis', 'space', 'pause'],
  splits: ['whole', 'sentence', 'clause', 'max'],
  defaults: { punctuation: recipeFixture().punctuation, gaps_ms: recipeFixture().gaps_ms, split: { mode: 'sentence', max_chars: 140, min_chars: 24 }, pause_ms: 250 },
})

export const lineFixture = (guid: string, order: number, crest: number | null, flag: LabFlag = null): LabLine => ({
  guid, cue: 'cue', order, text: `Line ${guid} text`, chars: 12, instruct: 'stern', ref: { wav: 'data/ref.wav' },
  current: crest === null ? null : { wav: `data/render/${guid}.wav`, seconds: 2.5, peak_db: -1, crest_db: crest, clip_runs: 0, flag },
})

export const takeFixture = (id: string, over: Partial<LabTake> = {}): LabTake => ({
  id, guid: 'g1', label: '', text: 'Line g1 text', recipe: recipeFixture(), seed: 7, pieces: [{ text: 'Line g1 text', seconds: 2, crest_db: 13, flag: null }],
  wav: `data/studio/lab/x/takes/${id}.wav`, metrics: { seconds: 2, peak_db: -1, crest_db: 13, clip_runs: 0, flag: null, model_peak: 0.9 },
  created: '2026-10-13 10:00:00', rating: 0, note: '', ...over,
})
