import { defineConfig } from '@playwright/test'

// One worker, files in name order: a-chain builds the state that c-mobile reuses.
// Tests in a file run in order; a failed test does not skip the next one (default mode).
export default defineConfig({
  testDir: './tests',
  outputDir: './test-results',
  workers: 1,
  fullyParallel: false,
  timeout: 6 * 60_000,
  expect: { timeout: 8_000 },
  reporter: [['list'], ['json', { outputFile: 'artifacts/report.json' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
    screenshot: 'off',
    trace: 'off',
    viewport: { width: 1366, height: 900 },
  },
})
