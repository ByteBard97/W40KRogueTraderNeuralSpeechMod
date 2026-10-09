import { mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { isAllowedOrigin, useFxBridge } from './useFxBridge'

describe('isAllowedOrigin', () => {
  it('accepts only the FX Lab on localhost', () => {
    expect(isAllowedOrigin('http://127.0.0.1:8908')).toBe(true)
    expect(isAllowedOrigin('http://localhost:8908')).toBe(true)
    for (const bad of ['http://127.0.0.1:8930', 'http://evil.example:8908', 'https://127.0.0.1:8908', '', 'null']) expect(isAllowedOrigin(bad)).toBe(false)
  })
})

function host(onPresetSaved: (n: string) => void) {
  const iframe = ref<HTMLIFrameElement | null>(null)
  let bridge!: ReturnType<typeof useFxBridge>
  const C = defineComponent({ setup() { bridge = useFxBridge({ iframe, onPresetSaved }); return () => h('div') } })
  return { w: mount(C), iframe, get bridge() { return bridge } }
}

describe('useFxBridge', () => {
  it('reports saved presets from the FX Lab and ignores other origins and message types', () => {
    const cb = vi.fn()
    const { w } = host(cb)
    window.dispatchEvent(new MessageEvent('message', { origin: 'http://127.0.0.1:8908', data: { type: 'studio:preset-saved', name: 'Servitor' } }))
    window.dispatchEvent(new MessageEvent('message', { origin: 'http://evil.example:8908', data: { type: 'studio:preset-saved', name: 'Bad' } }))
    window.dispatchEvent(new MessageEvent('message', { origin: 'http://127.0.0.1:8908', data: { type: 'something-else', name: 'X' } }))
    expect(cb).toHaveBeenCalledTimes(1)
    expect(cb).toHaveBeenCalledWith('Servitor')
    w.unmount()
    window.dispatchEvent(new MessageEvent('message', { origin: 'http://127.0.0.1:8908', data: { type: 'studio:preset-saved', name: 'After' } }))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('posts the clip to the iframe pinned to the FX Lab origin', () => {
    const post = vi.fn()
    const h2 = host(vi.fn())
    h2.iframe.value = { contentWindow: { postMessage: post } } as never
    const bytes = new ArrayBuffer(4)
    h2.bridge.sendClip('take', bytes)
    expect(post).toHaveBeenCalledWith({ type: 'studio:load-clip', name: 'take', bytes }, 'http://127.0.0.1:8908')
  })

  it('does nothing when the iframe is not there yet', () => {
    expect(() => host(vi.fn()).bridge.sendClip('x', new ArrayBuffer(1))).not.toThrow()
  })
})
