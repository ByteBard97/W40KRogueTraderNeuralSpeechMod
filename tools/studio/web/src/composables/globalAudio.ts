import { computed, reactive } from 'vue'
import { fileUrl } from '../utils/fileUrl'

/** The single <audio> element for the whole app. Everything that plays sound goes through this module. */
export const SPEEDS = [0.75, 1, 1.25, 1.5] as const
export const SEEK_SMALL_S = 1
export const SEEK_BIG_S = 5
const DEFAULT_VOLUME = 0.7
const TIME_EPSILON = 0.05

export interface NowPlaying {
  /** Identity of the clip: a repo path, or the URL for clips served from elsewhere. Matches what callers pass to `play`. */
  id: string | null
  url: string
  title: string
  subtitle: string
}

export interface Transport {
  prev?: () => void
  next?: () => void
}

const state = reactive({
  id: null as string | null,
  url: '',
  title: '',
  subtitle: '',
  isPlaying: false,
  current: 0,
  duration: 0,
  rate: 1 as number,
  loop: false,
  volume: DEFAULT_VOLUME,
  transport: {} as Transport,
})

let el: HTMLAudioElement | null = null

function element(): HTMLAudioElement {
  if (el) return el
  el = new Audio()
  el.volume = state.volume
  el.addEventListener('timeupdate', () => (state.current = el?.currentTime ?? 0))
  el.addEventListener('loadedmetadata', () => (state.duration = Number.isFinite(el?.duration) ? (el?.duration ?? 0) : 0))
  el.addEventListener('durationchange', () => (state.duration = Number.isFinite(el?.duration) ? (el?.duration ?? 0) : 0))
  el.addEventListener('play', () => (state.isPlaying = true))
  el.addEventListener('pause', () => (state.isPlaying = false))
  el.addEventListener('ended', () => {
    state.isPlaying = false
    state.current = state.duration
  })
  el.addEventListener('error', () => (state.isPlaying = false))
  return el
}

const baseName = (path: string) => (path.split('?')[0].split('/').pop() ?? path).replace(/\.[a-z0-9]+$/i, '')

export interface PlayMeta {
  title?: string
  subtitle?: string
}

function load(id: string, url: string | undefined, meta: PlayMeta) {
  const a = element()
  state.id = id
  state.url = url ?? fileUrl(id)
  state.title = meta.title ?? baseName(id)
  state.subtitle = meta.subtitle ?? id.split('?')[0]
  state.current = 0
  state.duration = 0
  a.src = state.url
  a.loop = state.loop
  a.playbackRate = state.rate
}

function startPlayback() {
  state.isPlaying = true
  void element()
    .play()
    .catch(() => (state.isPlaying = false))
}

function pause() {
  if (el) el.pause()
  state.isPlaying = false
}

function seek(seconds: number) {
  const a = element()
  const max = state.duration || Number.POSITIVE_INFINITY
  a.currentTime = Math.min(Math.max(seconds, 0), max)
  state.current = a.currentTime
}

export function useGlobalAudio() {
  const playing = computed(() => (state.isPlaying ? state.id : null))
  const hasClip = computed(() => state.id !== null)
  const progress = computed(() => (state.duration > TIME_EPSILON ? Math.min(state.current / state.duration, 1) : 0))
  const nowPlaying = computed<NowPlaying>(() => ({ id: state.id, url: state.url, title: state.title, subtitle: state.subtitle }))

  /** Load and play a clip. Playing the clip that is playing pauses it; playing a paused loaded clip resumes it. */
  function play(id: string, url?: string, meta: PlayMeta = {}) {
    if (state.id === id) {
      if (state.isPlaying) return pause()
      if (!el?.ended) return startPlayback()
    }
    load(id, url, meta)
    startPlayback()
  }
  /** Switch to another clip keeping the playhead, as a fraction of the clip or as absolute seconds. Plays if something was playing. */
  function switchTo(id: string, url?: string, meta: PlayMeta = {}, keep: 'fraction' | 'seconds' = 'fraction') {
    const wasPlaying = state.isPlaying
    const fraction = progress.value
    const seconds = state.current
    load(id, url, meta)
    const a = element()
    const apply = () => {
      if (keep === 'fraction') seek(fraction * state.duration)
      else seek(seconds)
    }
    if (state.duration > 0) apply()
    else a.addEventListener('loadedmetadata', apply, { once: true })
    if (wasPlaying) startPlayback()
  }
  function toggle() {
    if (!state.id) return
    if (state.isPlaying) pause()
    else if (el?.ended) {
      seek(0)
      startPlayback()
    } else startPlayback()
  }
  function stop() {
    pause()
  }
  const seekBy = (delta: number) => seek(state.current + delta)
  function setRate(rate: number) {
    state.rate = rate
    if (el) el.playbackRate = rate
  }
  function setLoop(on: boolean) {
    state.loop = on
    if (el) el.loop = on
  }
  function setVolume(v: number) {
    state.volume = Math.min(Math.max(v, 0), 1)
    if (el) el.volume = state.volume
  }
  function setTransport(t: Transport) {
    state.transport = t
  }
  function clearTransport(t: Transport) {
    if (state.transport === t) state.transport = {}
  }

  return {
    state,
    playing,
    hasClip,
    progress,
    nowPlaying,
    play,
    switchTo,
    toggle,
    stop,
    seek,
    seekBy,
    setRate,
    setLoop,
    setVolume,
    setTransport,
    clearTransport,
  }
}
