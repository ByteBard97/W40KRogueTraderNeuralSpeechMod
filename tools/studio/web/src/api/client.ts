import type {
  CloneRequest, LiveTake, Line, ModelState, SpeakerDetail, SpeakerSummary, Take, Verdict, VoiceProfile,
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
  cloneGenerate: (slug: string, body: CloneRequest) => post<Take>(`${S(slug)}/clone/generate`, body),
  takeFx: (slug: string, id: string, presets: string[]) => post<Take>(`${S(slug)}/takes/${id}/fx`, { presets }),
  takeRate: (slug: string, id: string, body: { rating?: number; note?: string }) => post<Take>(`${S(slug)}/takes/${id}/rate`, body),
}
