import { spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { existsSync, mkdtempSync, readdirSync, statSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const REPO = resolve(WEB, '..', '..', '..')
// Inside node_modules so it is ignored by git and never replaces the dist the real Studio serves.
const DIST = join(WEB, 'node_modules', '.e2e-dist')
const STACK = join(REPO, 'tools', 'studio', 'server', 'tests', 'run_mock_stack.py')
const VENDOR_PROBE = join(REPO, 'tools', 'fx_lab', 'vendor', 'faustwasm', 'index.js')
const READY_TIMEOUT_MS = 30_000
const POLL_MS = 150
const WATCHED = ['src', 'public', 'index.html', 'package.json', 'vite.config.ts', 'tsconfig.json']

function newest(path: string): number {
  if (!existsSync(path)) return 0
  const st = statSync(path)
  if (!st.isDirectory()) return st.mtimeMs
  return readdirSync(path).reduce((top, name) => Math.max(top, newest(join(path, name))), st.mtimeMs)
}

/** Rebuilds the web app only when a source file is newer than the last e2e build. Plain `vite build`: type errors are npm run build's job. */
function ensureBuilt(): void {
  const built = newest(join(DIST, 'index.html'))
  const changed = Math.max(...WATCHED.map((w) => newest(join(WEB, w))))
  if (built > changed) return
  console.log('e2e: web build is stale, building...')
  const r = spawnSync('npx', ['vite', 'build', '--outDir', DIST, '--emptyOutDir'], { cwd: WEB, stdio: 'inherit' })
  if (r.status !== 0) throw new Error('e2e: vite build failed')
}

function freePort(): Promise<number> {
  return new Promise((ok, fail) => {
    const s = createServer()
    s.once('error', fail)
    s.listen(0, '127.0.0.1', () => {
      const { port } = s.address() as { port: number }
      s.close(() => ok(port))
    })
  })
}

async function waitFor(url: string, child: ChildProcess): Promise<void> {
  const end = Date.now() + READY_TIMEOUT_MS
  while (Date.now() < end) {
    if (child.exitCode !== null) throw new Error(`e2e: the mock stack exited early with code ${child.exitCode}`)
    try {
      if ((await fetch(url)).ok) return
    } catch { /* not listening yet */ }
    await new Promise((r) => setTimeout(r, POLL_MS))
  }
  throw new Error(`e2e: the mock stack did not answer ${url} within ${READY_TIMEOUT_MS / 1000}s`)
}

export default async function globalSetup(): Promise<() => Promise<void>> {
  if (!existsSync(VENDOR_PROBE)) throw new Error('e2e: tools/fx_lab/vendor/faustwasm is missing; the page cannot compile Faust without it (see tools/fx_lab/vendor/README.md)')
  ensureBuilt()
  // A fresh, empty directory every run: the stack refuses to write fixtures into anything it did not create, and never sees data/.
  const tmp = mkdtempSync(join(tmpdir(), 'rt-studio-e2e-'))
  const root = join(tmp, 'root')
  const port = await freePort()
  const child = spawn('python3', [STACK, root, '--pedalboard', '--port', String(port), '--dist', DIST], { stdio: ['ignore', 'inherit', 'inherit'] })
  const base = `http://127.0.0.1:${port}`
  try {
    await waitFor(`${base}/api/pedalboard/blocks`, child)
  } catch (e) {
    child.kill()
    throw e
  }
  process.env.E2E_BASE_URL = base
  process.env.E2E_ROOT = root
  return async () => {
    child.kill()
  }
}
