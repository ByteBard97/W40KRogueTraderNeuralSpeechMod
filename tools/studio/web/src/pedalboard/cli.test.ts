// @vitest-environment node
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'
import { FIXTURE_CATALOG_PATH, FIXTURE_DIR, FIXTURE_LIB_PATH, seriesGraph } from './fixtures/testkit'

const WEB_DIR = resolve(FIXTURE_DIR, '../../..')
const VITE_NODE = join(WEB_DIR, 'node_modules/.bin/vite-node')
const CLI_TIMEOUT_MS = 60_000
const work = mkdtempSync(join(tmpdir(), 'pedalboard-cli-'))

function runCli(graph: unknown) {
  const file = join(work, `g${Math.random().toString(36).slice(2)}.json`)
  writeFileSync(file, JSON.stringify(graph))
  return spawnSync(
    VITE_NODE,
    ['src/pedalboard/cli.ts', '--', file, '--catalog', FIXTURE_CATALOG_PATH, '--lib', FIXTURE_LIB_PATH],
    { cwd: WEB_DIR, encoding: 'utf8', timeout: CLI_TIMEOUT_MS },
  )
}

describe('cli', () => {
  it('prints {code, controls, params} for a valid graph', () => {
    const r = runCli(seriesGraph())
    expect(r.status, r.stderr).toBe(0)
    const out = JSON.parse(r.stdout)
    expect(Object.keys(out).sort()).toEqual(['code', 'controls', 'params'])
    expect(out.code).toContain('process = vgroup("fx"')
    expect(out.params).toMatchObject({ n2_Gain_dB: 0, n2_on: 1, n4_Output_dB: 0 })
    expect(out.controls.map((c: { key: string }) => c.key)).toContain('n3_Gain_dB')
  }, CLI_TIMEOUT_MS)

  it('exits 1 with the issues on stderr for an invalid graph', () => {
    const g = seriesGraph()
    g.edges.pop()
    const r = runCli(g)
    expect(r.status).toBe(1)
    expect(r.stdout).toBe('')
    expect(JSON.parse(r.stderr).map((i: { code: string }) => i.code)).toContain('missing-input')
  }, CLI_TIMEOUT_MS)
})
