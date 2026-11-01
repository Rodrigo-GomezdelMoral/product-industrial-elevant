import { defineConfig } from '@playwright/test'

declare const process: { env: Record<string, string | undefined> }
const live = process.env.ELEVANT_URL

export default defineConfig({
  testDir: 'tests',
  testMatch: live ? 'live.spec.ts' : 'web.spec.ts',
  timeout: live ? 900_000 : 120_000,
  use: { baseURL: live ?? 'http://127.0.0.1:4173', acceptDownloads: true, headless: !live },
  webServer: live ? undefined : [
    {
      command: 'python -m uvicorn app.main:app --port 8000',
      cwd: '..',
      url: 'http://127.0.0.1:8000/healthz',
      env: { ELEVANT_DOUBLES: 'true' },
      reuseExistingServer: true,
    },
    { command: 'npm run preview', url: 'http://127.0.0.1:4173', reuseExistingServer: true },
  ],
})
