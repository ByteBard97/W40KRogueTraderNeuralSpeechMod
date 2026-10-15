// Compiles a Faust program with the unmodified FaustWasm files served next to the page (faustwasm/, libfaust-wasm/).
import type { MakeNode } from '../composables/useGraphEngine'

const MODULE_PATH = 'faustwasm/index.js'
const MODULE_DIR = 'faustwasm/'

/**
 * FaustWasm finds libfaust at `../libfaust-wasm/` relative to document.baseURI, which is only right when the page is at
 * the site root. Pointing <base> at faustwasm/ for the synchronous start of the first compile makes that path resolve
 * to our sibling folder wherever the demo is hosted, without touching the vendored file.
 */
export const makeDemoNode: MakeNode = async (ctx, name, code) => {
  const errs: string[] = []
  const original = console.error
  console.error = (...a: unknown[]) => { errs.push(a.join(' ')); original(...a) }
  try {
    const mod = await import(/* @vite-ignore */ new URL(MODULE_PATH, document.baseURI).href)
    const base = document.createElement('base')
    base.href = new URL(MODULE_DIR, document.baseURI).href
    document.head.prepend(base)
    let pending: Promise<unknown>
    try { pending = new mod.FaustDspGenerator().createFaustNode(ctx, name, code) } finally { base.remove() }
    return (await pending) as Awaited<ReturnType<MakeNode>>
  } catch (e) {
    throw new Error([...errs, String(e)].join('\n'))
  } finally {
    console.error = original
  }
}
