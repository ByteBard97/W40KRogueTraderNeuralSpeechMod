// Standalone static build of the pedalboard editor (see demo/README.md). Not used by the Studio's own build.
import vue from '@vitejs/plugin-vue'
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'
import { readDemoData } from './demo/buildData'

const here = dirname(fileURLToPath(import.meta.url))
const FX_LAB = resolve(here, '../../fx_lab')
const VENDOR = join(FX_LAB, 'vendor')
const VENDOR_DIRS = ['faustwasm', 'libfaust-wasm']
/** Type declarations are not needed at run time. */
const SKIP = /\.d\.c?ts$/
const ENTRY = 'demo.html'

const vendorFiles = () => VENDOR_DIRS.flatMap((d) => readdirSync(join(VENDOR, d)).filter((f) => !SKIP.test(f)).map((f) => `${d}/${f}`))
const MIME: Record<string, string> = { '.js': 'text/javascript', '.wasm': 'application/wasm', '.json': 'application/json' }

function demoAssets(): Plugin {
  const extra: Record<string, string> = {
    'THIRD_PARTY_NOTICES.md': join(here, 'demo/THIRD_PARTY_NOTICES.md'),
    'licenses/faustwasm-COPYING.txt': join(here, 'demo/licenses/faustwasm-COPYING.txt'),
  }
  return {
    name: 'demo-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0]
        const rel = url.replace(/^\//, '')
        if (rel === 'demo-data.json') {
          res.setHeader('Content-Type', MIME['.json'])
          res.end(JSON.stringify(readDemoData(FX_LAB)))
        } else if (vendorFiles().includes(rel)) {
          res.setHeader('Content-Type', MIME[rel.slice(rel.lastIndexOf('.'))] ?? 'application/octet-stream')
          res.end(readFileSync(join(VENDOR, rel)))
        } else next()
      })
    },
    generateBundle: { order: 'post', handler(_, bundle) {
      // Hosts serve index.html at the folder URL; the source entry has to be demo.html for Vite.
      const page = bundle[ENTRY]
      if (page) { delete bundle[ENTRY]; page.fileName = 'index.html'; bundle['index.html'] = page }
      this.emitFile({ type: 'asset', fileName: 'demo-data.json', source: JSON.stringify(readDemoData(FX_LAB)) })
      for (const rel of vendorFiles()) this.emitFile({ type: 'asset', fileName: rel, source: readFileSync(join(VENDOR, rel)) })
      for (const [out, src] of Object.entries(extra)) this.emitFile({ type: 'asset', fileName: out, source: readFileSync(src) })
    } },
  }
}

export default defineConfig({
  base: './',
  publicDir: false, // the Studio's font files are not referenced by the demo
  plugins: [vue(), demoAssets()],
  resolve: {
    // The store imports the Studio's HTTP client; the demo swaps in the static one without touching the store.
    alias: [{ find: /^(\.\.\/)+api\/client$/, replacement: resolve(here, 'src/demo/demoApi.ts') }],
  },
  build: { outDir: 'dist-demo', emptyOutDir: true, rollupOptions: { input: resolve(here, ENTRY) } },
  server: { open: `/${ENTRY}` },
  test: { environment: 'happy-dom', globals: true },
})
