import type {
  MatchFilter, MatchValue, QaFacets, QaFilter, QaPage, QaRun, QaVerdictBody, MatchesPage, FxLabels, FxPresetInfo, FxPreview, FxWritten, OverrideBody, PoolSummary, QueueEntry, RoutesPage, SpotSample,
  CloneRequest, RegisterAllResult, LiveTake, Line, ModelState, SpeakerDetail, SpeakerSummary, Take, Verdict, VoiceProfile,
} from './types'

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
  designOrder: (slug: string, order: string[]) => post<object>(`${S(slug)}/design/order`, { order }),
  designDescription: (slug: string, description: string) => post<object>(`${S(slug)}/design/description`, { description }),
  register: (slug: string) => post<{ registered: string[] }>(`${S(slug)}/register`),
  registerAll: () => post<RegisterAllResult>('/api/speakers/register-all'),
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
  poolOverride: (body: OverrideBody) => post<{ changed: number }>('/api/pools/routes', body),
  poolRename: (slot: string, name: string) => post<object>(`/api/pools/slots/${encodeURIComponent(slot)}/rename`, { name }),
  poolMerge: (slot: string, into: string) => post<{ changed: number }>(`/api/pools/slots/${encodeURIComponent(slot)}/merge`, { into }),
  poolSpot: (slot: string, seed?: number) => request<SpotSample>(`/api/pools/spot-check/${encodeURIComponent(slot)}${seed === undefined ? '' : `?seed=${seed}`}`),
  poolSpotRecord: (slot: string, results: Record<string, boolean>) => post<{ checked: number; wrong: number }>(`/api/pools/spot-check/${encodeURIComponent(slot)}`, { results }),
  fxLibrary: () => request<FxPresetInfo[]>('/api/fx/library'),
  fxLabels: () => request<FxLabels>('/api/fx/labels'),
  fxSaveLabels: (labels: FxLabels) => post<FxLabels>('/api/fx/labels', labels),
  fxPreview: () => request<FxPreview>('/api/fx/assignments/preview'),
  fxWrite: () => post<FxWritten>('/api/fx/assignments'),
  matches: (f: MatchFilter & { offset?: number; limit?: number }) => {
    const qs = Object.entries(f).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    return request<MatchesPage>(`/api/matches${qs ? `?${qs}` : ''}`)
  },
  matchDecision: (id: string, value: MatchValue) => post<{ pools_rebuilt: boolean; queue_entries?: number }>('/api/matches/decision', { id, value }),
  qaRuns: () => request<QaRun[]>('/api/qa/runs'),
  qaFacets: (run: string) => request<QaFacets>(`/api/qa/facets?run=${encodeURIComponent(run)}`),
  qaClips: (run: string, f: QaFilter & { offset?: number; limit?: number; exclude?: string }) => {
    const qs = Object.entries({ run, ...f }).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
    return request<QaPage>(`/api/qa/clips?${qs}`)
  },
  qaVerdict: (body: QaVerdictBody) => post<object>('/api/qa/verdict', body),
}
