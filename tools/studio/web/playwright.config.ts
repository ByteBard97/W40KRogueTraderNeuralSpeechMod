import { existsSync, readdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { defineConfig } from '@playwright/test'

// Prefer the Chromium the Playwright MCP already downloaded (browser binaries are not part of the repo). Without one, Playwright's own
// download is used: `npx playwright install chromium`.
function cachedChromium(): string | undefined {
  const base = join(process.env.PLAYWRIGHT_BROWSERS_PATH ?? join(homedir(), '.cache', 'ms-playwright'))
  if (!existsSync(base)) return undefined
  const dirs = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d)).sort((a, b) => Number(b.split('-')[1]) - Number(a.split('-')[1]))
  for (const d of dirs) {
    const exe = join(base, d, 'chrome-linux64', 'chrome')
    if (existsSync(exe)) return exe
  }
  return undefined
}

export default defineConfig({
  testDir: 'e2e',
  globalSetup: './e2e/globalSetup.ts',
  // One worker: all specs share one mock server and the page compiles Faust in WebAssembly, which is CPU heavy.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  // Traces and screenshots on failure stay in these two folders, which are git-ignored.
  outputDir: 'test-results',
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    viewport: { width: 1600, height: 1000 },
    colorScheme: 'dark',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath: cachedChromium(),
      // The transport plays audio without a click in the test, and the engine's AudioContext must be allowed to start.
      args: ['--autoplay-policy=no-user-gesture-required'],
    },
  },
})
