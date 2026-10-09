import { onBeforeUnmount, onMounted, type Ref } from 'vue'

export const FX_LAB_PORT = 8908
const LOCAL_HOSTS = ['127.0.0.1', 'localhost']

export const fxLabUrl = (port = FX_LAB_PORT) => `http://127.0.0.1:${port}/`

/** Only messages from the FX Lab page itself are trusted. */
export function isAllowedOrigin(origin: string, port = FX_LAB_PORT): boolean {
  return LOCAL_HOSTS.some((h) => origin === `http://${h}:${port}`)
}

export function useFxBridge(opts: { iframe: Ref<HTMLIFrameElement | null>; onPresetSaved: (name: string) => void; port?: number }) {
  const port = opts.port ?? FX_LAB_PORT
  function onMessage(e: MessageEvent) {
    if (!isAllowedOrigin(e.origin, port)) return
    if (e.data?.type === 'studio:preset-saved' && typeof e.data.name === 'string') opts.onPresetSaved(e.data.name)
  }
  onMounted(() => window.addEventListener('message', onMessage))
  onBeforeUnmount(() => window.removeEventListener('message', onMessage))

  function sendClip(name: string, bytes: ArrayBuffer) {
    opts.iframe.value?.contentWindow?.postMessage({ type: 'studio:load-clip', name, bytes }, `http://127.0.0.1:${port}`)
  }
  return { sendClip }
}
