import type {
  MatchFilter, MatchValue, QaFacets, QaFilter, QaPage, QaRun, QaVerdictBody, MatchesPage, FxLabels, FxPresetInfo, FxPreview, FxWritten, FxUsage, FxDiff, FxBackup, FxRestored, OverrideBody, OverrideResult, NewSlotBody, PoolSlot, PoolSummary, QueueEntry, RoutesPage, SpotSample,
  AssignmentsPage, PedalboardBlocks, PedalboardGraphInfo, PedalboardSaveBody, PedalboardSaved, PedalboardStarter, RtVoicesPage, Bg3Voice, LabelValue, LabelsInfo, VoiceLabels, CastAudition, CastPage, CastRegistered, CloneRequest, RegisterAllResult, LiveTake, Line, ModelState, SpeakerDetail, SpeakerSummary, Take, Verdict, VoiceProfile,
} from './types'
import type { Graph } from '../pedalboard/types'
import type { JobView } from './jobs'
import type { LabJob, LabLexiconHit, LabLines, LabOptions, LabPrepared, LabRealClip, LabOpusPreview, LabRecipe, LabRenderBody, LabSpeaker, LabTake } from './labTypes'

export class ApiRequestError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiRequestError(res.status, (body as { error?: string }).error ?? `HTTP ${res.status}`)
  return body as T
}

const post = <T>(url: string, body: unknown = {}) =>
  request<T>(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

const L = (speaker: string) => `/api/lab/${encodeURIComponent(speaker)}`
const S = (slug: string) => `/api/speakers/${encodeURIComponent(slug)}`

export const api = {
  health: () => request<{ state: ModelState }>('/api/model/health'),
  speakers: () => request<SpeakerSummary[]>('/api/speakers'),
  speaker: (slug: string) => request<SpeakerDetail>(S(slug)),
  lines: (slug: string) => request<Line[]>(`${S(slug)}/lines`),
  takes: (slug: string) => request<Take[]>(`${S(slug)}/takes`),
  fxPresets: () => request<string[]>('/api/fx/presets'),
  saveProfile: (slug: string, body: Partial<VoiceProfile>) => post<VoiceProfile>(`${S(slug)}/profile`, body),
  setActive: (slug: string) => post<{ active: string }>(`${S(slug)}/active`),
  designGenerate: (slug: string, body: { description?: string; seed?: string; cfg?: number; timesteps?: number }) =>
    post<LiveTake>(`${S(slug)}/design/generate`, body),
  designKeep: (slug: string, body: Partial<LiveTake>) => post<{ cand: string }>(`${S(slug)}/design/keep`, body),
  designVerdict: (slug: string, body: { cand: string; pick?: boolean } & Verdict) => post<object>(`${S(slug)}/design/verdict`, body),
  designOrder: (slug: string, order: string[], followRank = false) => post<object>(`${S(slug)}/design/order`, { order, follow_rank: followRank }),
  designDescription: (slug: string, description: string) => post<object>(`${S(slug)}/design/description`, { description }),
  register: (slug: string) => post<{ registered: string[] }>(`${S(slug)}/register`),
  registerAll: () => post<RegisterAllResult>('/api/speakers/register-all'),
  jobSubmit: (slug: string, kind: 'clone' | 'design', body: { items: object[]; fx?: string[]; label?: string }) => post<JobView>(`${S(slug)}/${kind}/jobs`, body),
  jobsActive: (slug: string) => request<JobView[]>(`/api/jobs?active=1&slug=${encodeURIComponent(slug)}`),
  job: (id: string) => request<JobView>(`/api/jobs/${encodeURIComponent(id)}`),
  jobCancel: (id: string) => post<JobView>(`/api/jobs/${encodeURIComponent(id)}/cancel`),
  cloneGenerate: (slug: string, body: CloneRequest) => post<Take>(`${S(slug)}/clone/generate`, body),
  takeFx: (slug: string, id: string, presets: string[]) => post<Take>(`${S(slug)}/takes/${id}/fx`, { presets }),
  takeRate: (slug: string, id: string, body: { rating?: number; note?: string }) => post<Take>(`${S(slug)}/takes/${id}/rate`, body),
  pools: () => request<PoolSummary>('/api/pools'),
  poolsRebuild: (body: { threshold?: number } = {}) => post<PoolSummary>('/api/pools/rebuild', body),
  poolRoutes: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = Object.entries(params).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    return request<RoutesPage>(`/api/pools/routes${qs ? `?${qs}` : ''}`)
  },
  poolQueue: () => request<QueueEntry[]>('/api/pools/queue'),
  poolOverride: (body: OverrideBody) => post<OverrideResult>('/api/pools/routes', body),
  poolRestore: (previous: Record<string, unknown>) => post<{ changed: number }>('/api/pools/routes/restore', { previous }),
  poolUnmerge: (slot: string) => post<{ changed: number; slot?: PoolSlot }>(`/api/pools/slots/${encodeURIComponent(slot)}/unmerge`, {}),
  poolCreateSlot: (body: NewSlotBody) => post<PoolSlot>('/api/pools/slots', body),
  poolRename: (slot: string, name: string) => post<object>(`/api/pools/slots/${encodeURIComponent(slot)}/rename`, { name }),
  poolMerge: (slot: string, into: string) => post<{ changed: number }>(`/api/pools/slots/${encodeURIComponent(slot)}/merge`, { into }),
  poolSpot: (slot: string, seed?: number) => request<SpotSample>(`/api/pools/spot-check/${encodeURIComponent(slot)}${seed === undefined ? '' : `?seed=${seed}`}`),
  poolSpotRecord: (slot: string, results: Record<string, boolean>) => post<{ checked: number; wrong: number }>(`/api/pools/spot-check/${encodeURIComponent(slot)}`, { results }),
  fxLibrary: () => request<FxPresetInfo[]>('/api/fx/library'),
  fxLabels: () => request<FxLabels>('/api/fx/labels'),
  fxSaveLabels: (labels: FxLabels) => post<FxLabels>('/api/fx/labels', labels),
  fxPreview: () => request<FxPreview>('/api/fx/assignments/preview'),
  fxWrite: () => post<FxWritten>('/api/fx/assignments'),
  fxUsage: () => request<FxUsage>('/api/fx/labels/usage'),
  fxDiff: () => request<FxDiff>('/api/fx/assignments/diff'),
  fxBackups: () => request<FxBackup[]>('/api/fx/backups'),
  fxRestore: (backup: string) => post<FxRestored>('/api/fx/restore', { backup }),
  matches: (f: MatchFilter & { offset?: number; limit?: number }) => {
    const qs = Object.entries(f).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    return request<MatchesPage>(`/api/matches${qs ? `?${qs}` : ''}`)
  },
  matchDecision: (id: string, value: MatchValue, rebuild = true) =>
    post<{ pools_rebuilt: boolean; pools_stale?: boolean; queue_entries?: number }>('/api/matches/decision', rebuild ? { id, value } : { id, value, rebuild: false }),
  matchesRebuild: () => post<{ pools_rebuilt: boolean; queue_entries?: number }>('/api/matches/rebuild'),
  qaRuns: () => request<QaRun[]>('/api/qa/runs'),
  qaFacets: (run: string) => request<QaFacets>(`/api/qa/facets?run=${encodeURIComponent(run)}`),
  qaClips: (run: string, f: QaFilter & { offset?: number; limit?: number; exclude?: string }) => {
    const qs = Object.entries({ run, ...f }).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    return request<QaPage>(`/api/qa/clips?${qs}`)
  },
  qaVerdict: (body: QaVerdictBody) => post<object>('/api/qa/verdict', body),
  rtVoices: () => request<RtVoicesPage>('/api/rtvoices'),
  rtVoiceLabelSet: (slug: string, key: string, value: LabelValue | null) => post<VoiceLabels>('/api/rtvoices/labels', { slug, key, value }),
  assignments: () => request<AssignmentsPage>('/api/assignments'),
  assignmentsRun: () => post<Record<string, number>>('/api/assignments/run'),
  assignmentOverride: (key: string, bg3: string | null) => post<object>('/api/assignments/override', { key, bg3 }),
  casting: () => request<CastPage>('/api/casting'),
  castingVoices: () => request<Bg3Voice[]>('/api/casting/bg3'),
  castAssign: (speaker: string, bg3: string | null) => post<{ speaker: string; bg3: string | null }>('/api/casting/assign', { speaker, bg3 }),
  castPortrait: (speaker: string, portrait: string | null) => post<{ speaker: string; portrait: string | null }>('/api/casting/portrait', { speaker, portrait }),
  castAudition: (speaker: string, bg3: string, ref = 0, line = 0) => post<CastAudition>('/api/casting/audition', { speaker, bg3, ref, line }),
  castRegister: () => post<CastRegistered>('/api/casting/register'),
  castLabels: () => request<LabelsInfo>('/api/casting/labels'),
  castLabelSet: (slug: string, key: string, value: LabelValue | null) => post<VoiceLabels>('/api/casting/labels', { slug, key, value }),
  labOptions: () => request<LabOptions>('/api/lab/options'),
  labSpeakers: () => request<LabSpeaker[]>('/api/lab/speakers'),
  labLines: (speaker: string) => request<LabLines>(`${L(speaker)}/lines`),
  labPrepare: (body: { speaker: string; guid?: string; text?: string; recipe: LabRecipe }) => post<LabPrepared>('/api/lab/prepare', body),
  labRender: (body: LabRenderBody) => post<LabJob>('/api/lab/render', body),
  labJob: (id: string) => request<LabJob>(`/api/lab/jobs/${encodeURIComponent(id)}`),
  labJobCancel: (id: string) => post<LabJob>(`/api/lab/jobs/${encodeURIComponent(id)}/cancel`),
  labTakes: (speaker: string, guid?: string) => request<LabTake[]>(`${L(speaker)}/takes${guid ? `?guid=${encodeURIComponent(guid)}` : ''}`),
  labTakeUpdate: (speaker: string, id: string, body: { rating?: number; note?: string; hidden?: boolean }) => post<LabTake>(`${L(speaker)}/takes/${encodeURIComponent(id)}`, body),
  labRecipes: () => request<LabRecipe[]>('/api/lab/recipes'),
  labRecipeSave: (name: string, recipe: LabRecipe) => post<LabRecipe[]>('/api/lab/recipes', { name, recipe }),
  labRealClips: (q: string, limit = 12) => request<LabRealClip[]>(`/api/lab/real-clips?q=${encodeURIComponent(q)}&limit=${limit}`),
  labOpus: (wav: string, kbps: number) => post<LabOpusPreview>('/api/lab/opus', { wav, kbps }),
  labLexicon: (q: string) => request<LabLexiconHit[]>(`/api/lab/lexicon?q=${encodeURIComponent(q)}`),
  pedalboardBlocks: () => request<PedalboardBlocks>('/api/pedalboard/blocks'),
  pedalboardGraphs: () => request<PedalboardGraphInfo[]>('/api/pedalboard/graphs'),
  pedalboardGraph: (name: string) => request<Graph>(`/api/pedalboard/graphs/${encodeURIComponent(name)}`),
  pedalboardSave: (body: PedalboardSaveBody) => post<PedalboardSaved>('/api/pedalboard/graphs', body),
  pedalboardStarters: () => request<PedalboardStarter[]>('/api/pedalboard/starters'),
}
